import { NextRequest, NextResponse } from 'next/server';
import client from '@/lib/minioClient';
import archiver from 'archiver';
import { PassThrough } from 'stream';

export async function GET(
    request: NextRequest,
    { params }: { params?: { params: string[] } }
) {
    const parts = await params?.params ?? [];
    const [dataDir, id, fileName] = parts;

    // Validate dataDir
    if (!dataDir || !['low-bandwidth', 'high-bandwidth'].includes(dataDir)) {
        return NextResponse.json(
            { error: 'Invalid dataDir. Only "low-bandwidth" and "high-bandwidth" are supported.' },
            { status: 400 }
        );
    }

    // No ID: list available folders with metadata
    if (!id) {
        try {
            const allObjs: Array<{ name: string; size: number; lastModified: Date; etag: string }> = [];
            for await (const obj of client.listObjectsV2(dataDir, '', true)) {
                allObjs.push(obj);
            }

            const grouped = allObjs.reduce<Record<string, any>>((acc, obj) => {
                const [folder, fname] = obj.name.split('/');
                if (!folder || !fname) return acc;
                if (!acc[folder]) acc[folder] = { id: folder };

                if (fname === 'result.json') {
                    acc[folder].result = {
                        name: obj.name,
                        size: obj.size,
                        lastModified: obj.lastModified,
                        etag: obj.etag,
                    };
                } else if (['thumbnail.jpg', 'annotated.jpg'].includes(fname)) {
                    acc[folder].image = {
                        name: obj.name,
                        size: obj.size,
                        lastModified: obj.lastModified,
                        etag: obj.etag,
                    };
                }
                return acc;
            }, {});

            return NextResponse.json(Object.values(grouped));
        } catch (err: any) {
            console.error('MinIO list error:', err);
            return NextResponse.json({ error: 'Could not list objects' }, { status: 500 });
        }
    }

    // Zip request: bundle all files under a folder
    if (fileName === 'zip') {
        const pass = new PassThrough();
        const archive = archiver('zip', { zlib: { level: 9 } });
        archive.on('error', err => {
            console.error('Archive error:', err);
            pass.destroy(err);
        });
        archive.pipe(pass);

        for await (const obj of client.listObjectsV2(dataDir, `${id}/`, true)) {
            const name = obj.name.split('/').slice(1).join('/');
            if (!name) continue;
            const stream = await client.getObject(dataDir, obj.name);
            archive.append(stream, { name });
        }
        await archive.finalize();

        return new NextResponse(pass, {
            status: 200,
            headers: {
                'Content-Type': 'application/zip',
                'Content-Disposition': `attachment; filename=${id}.zip`,
            },
        });
    }

    // JSON file request
    if (fileName && fileName.endsWith('.json')) {
        const objectKey = `${id}/${fileName}`;
        try {
            const stream = await client.getObject(dataDir, objectKey);
            const bufs: Buffer[] = [];
            for await (const chunk of stream) bufs.push(chunk);
            const json = JSON.parse(Buffer.concat(bufs).toString('utf-8'));
            return NextResponse.json(json);
        } catch (err: any) {
            console.error('Error fetching JSON:', err);
            return NextResponse.json({ error: 'JSON file not found' }, { status: 404 });
        }
    }

    // Default: return image (thumbnail or annotated)
    const imageFile = dataDir === 'high-bandwidth' ? 'annotated.jpg' : 'thumbnail.jpg';
    const objectKey = `${id}/${imageFile}`;
    try {
        const imageStream = await client.getObject(dataDir, objectKey);
        return new NextResponse(imageStream, {
            status: 200,
            headers: { 'Content-Type': 'image/jpeg' },
        });
    } catch (err: any) {
        console.error('Error fetching image:', err);
        return NextResponse.json({ error: 'File not found' }, { status: 404 });
    }
}
