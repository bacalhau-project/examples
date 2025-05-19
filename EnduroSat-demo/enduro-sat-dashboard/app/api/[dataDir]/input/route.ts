import { NextResponse } from 'next/server';
import { readdir } from 'fs/promises';
import path from 'path';

const DATA_DIR_REGEX = /^[\w-]+$/;

export async function GET(
    _request: Request,
    { params }: { params: { dataDir: string } }
) {
    const { dataDir } = await params;

    if (!DATA_DIR_REGEX.test(dataDir)) {
        return NextResponse.json(
            { error: 'Invalid data directory name' },
            { status: 400 }
        );
    }

    try {
        const inputPath = path.resolve(
            process.cwd(),
            `../${dataDir}/input`
        );
        const files = await readdir(inputPath);

        const images = files
            .filter((file) => {
                const ext = path.extname(file).toLowerCase();
                if (!['.bmp', '.jpg', '.jpeg'].includes(ext)) return false;
                if (file.toLowerCase() === 'thumbnail.jpg') return false;
                return true;
            })
            .map((file) => path.basename(file, path.extname(file)));

        return NextResponse.json({ images });
    } catch (err) {
        console.error(`Error reading ${dataDir}/input:`, err);
        return NextResponse.json(
            { error: `Unable to read input directory for ${dataDir}` },
            { status: 500 }
        );
    }
}
