import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export async function GET(
    request: Request,
    { params }: { params: { dataDir: string; bandwidth: string; image: string } }
) {
    const { dataDir, bandwidth, image } = await params;

    // … your validation here …

    const fileName = bandwidth === 'HIGH_bandwidth'
        ? 'annotated.jpg'
        : 'thumbnail.jpg';

    const filePath = path.resolve(
        process.cwd(),
        `../${dataDir}/output/${bandwidth}/${image}/${fileName}`
    );

    try {
        const fileBuf = await fs.readFile(filePath);
        return new NextResponse(fileBuf, {
            status: 200,
            headers: {
                'Content-Type': 'image/jpeg',
                'Content-Length': String(fileBuf.length),
            },
        });
    } catch (e) {
        console.error(e);
        return NextResponse.json({ error: 'File not found' }, { status: 404 });
    }
}
