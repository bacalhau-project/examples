import { NextRequest, NextResponse } from 'next/server';
import client from '@/lib/minioClient';
import archiver from 'archiver';
import { PassThrough } from 'stream';

export async function GET(
    request: NextRequest,
    context: { params: Promise<{ params?: string[] }> }
) {
    // 1) Await the dynamic params
    const { params: parts = [] } = await context.params;
    const [dataDir, id, fileName] = parts;

    // 2) Validate dataDir
    if (!dataDir || !['low-bandwidth', 'high-bandwidth'].includes(dataDir)) {
        return NextResponse.json(
            { error: 'Invalid dataDir. Only "low-bandwidth" and "high-bandwidth" are supported.' },
            { status: 400 }
        );
    }

    // 3) No ID: list folders with metadata
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
    // 4) Zip request
    else if (fileName === 'zip') {
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
    // 5) JSON file request (guard against zero-byte content)
    else if (fileName?.endsWith('.json')) {
        const jsonKey = `${id}/${fileName}`;
        try {
            const stream = await client.getObject(dataDir, jsonKey);
            const bufs: Buffer[] = [];
            for await (const chunk of stream) bufs.push(chunk);

            const buf = Buffer.concat(bufs);
            if (buf.length === 0) {
                // empty file → No Content
                return new NextResponse(null, { status: 204 });
            }

            const data = JSON.parse(buf.toString('utf-8'));
            return NextResponse.json(data);
        } catch (err: any) {
            console.error('Error fetching JSON:', err);
            return NextResponse.json({ error: 'JSON file not found' }, { status: 404 });
        }
    }
    // 6) Default: image (thumbnail or annotated)
    else {
        const imageFile = dataDir === 'high-bandwidth' ? 'annotated.jpg' : 'thumbnail.jpg';
        const imageKey = `${id}/${imageFile}`;
        try {
            const imageStream = await client.getObject(dataDir, imageKey);
            return new NextResponse(imageStream, {
                status: 200,
                headers: { 'Content-Type': 'image/jpeg' },
            });
        } catch (err: any) {
            console.error('Error fetching image:', err);
            return NextResponse.json({ error: 'File not found' }, { status: 404 });
        }
    }
}
