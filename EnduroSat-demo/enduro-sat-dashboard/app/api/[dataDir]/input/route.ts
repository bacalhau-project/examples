import { NextResponse } from 'next/server';
import { readdir } from 'fs/promises';
import path from 'path';

const DATA_DIR_REGEX = /^[\w-]+$/;

export async function GET(
    _request: Request,
    { params }: { params: { dataDir: string } }
) {
    const dataDir = params.dataDir;

    if (!DATA_DIR_REGEX.test(dataDir)) {
        return NextResponse.json({ error: 'Invalid data directory name' }, { status: 400 });
    }

    try {
        const inputPath = path.join('/app/data', dataDir, 'input');
        const files = await readdir(inputPath);
        const images = files
            .filter(file => {
                const ext = path.extname(file).toLowerCase();
                return ['.bmp', '.jpg', '.jpeg'].includes(ext) && file.toLowerCase() !== 'thumbnail.jpg';
            })
            .map(file => path.basename(file, path.extname(file)));

        return NextResponse.json({ images });
    } catch {
        return NextResponse.json(
            { error: `Unable to read input directory for ${dataDir}` },
            { status: 500 }
        );
    }
}
