import { NextResponse } from 'next/server';
import { readdir, stat } from 'fs/promises';
import path from 'path';

const DATA_DIR_REGEX = /^[\w-]+$/;
const BANDWIDTH_VALUES = ['HIGH_bandwidth', 'LOW_bandwidth'] as const;

export async function GET(
    _req: Request,
    { params }: { params: { dataDir: string; bandwidth: string } }
) {
    const { dataDir, bandwidth } = params;

    if (!DATA_DIR_REGEX.test(dataDir) || !BANDWIDTH_VALUES.includes(bandwidth as any)) {
        return NextResponse.json({ error: 'Invalid dataDir or bandwidth' }, { status: 400 });
    }

    const baseDir = path.join('/app/data', dataDir, 'output', bandwidth);

    let entries: string[];
    try {
        entries = await readdir(baseDir);
    } catch {
        return NextResponse.json({ images: [] });
    }

    const checkFile = bandwidth === 'HIGH_bandwidth' ? 'annotated.jpg' : 'thumbnail.jpg';

    const images: string[] = [];
    for (const name of entries) {
        const dirPath = path.join(baseDir, name);
        try {
            const st = await stat(dirPath);
            if (!st.isDirectory()) continue;
            const candidate = path.join(dirPath, checkFile);
            if ((await stat(candidate)).isFile()) {
                images.push(name);
            }
        } catch {
            continue;
        }
    }

    return NextResponse.json({ images });
}
