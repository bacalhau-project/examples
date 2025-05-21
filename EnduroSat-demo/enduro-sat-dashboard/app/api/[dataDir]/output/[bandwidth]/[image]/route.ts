import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

const DATA_DIR_REGEX = /^[\w-]+$/;
const BANDWIDTH_VALUES = ['HIGH_bandwidth', 'LOW_bandwidth'] as const;
const IMAGE_REGEX = /^[\w-]+$/;

export async function GET(
    _request: Request,
    { params }: { params: { dataDir: string; bandwidth: string; image: string } }
) {
    const { dataDir, bandwidth, image } = params;

    if (
        !DATA_DIR_REGEX.test(dataDir) ||
        !BANDWIDTH_VALUES.includes(bandwidth as any) ||
        !IMAGE_REGEX.test(image)
    ) {
        return NextResponse.json({ error: 'Invalid parameters' }, { status: 400 });
    }

    const fileName = bandwidth === 'HIGH_bandwidth' ? 'annotated.jpg' : 'thumbnail.jpg';
    const filePath = path.join('/app/data', dataDir, 'output', bandwidth, image, fileName);

    try {
        const fileBuf = await fs.readFile(filePath);
        return new NextResponse(fileBuf, {
            status: 200,
            headers: {
                'Content-Type': 'image/jpeg',
                'Content-Length': String(fileBuf.length)
            }
        });
    } catch {
        return NextResponse.json({ error: 'File not found' }, { status: 404 });
    }
}
