// app/api/[dataDir]/output/[bandwidth]/route.ts
import { NextResponse } from 'next/server';
import { readdir, stat } from 'fs/promises';
import path from 'path';

const DATA_DIR_REGEX = /^[\w-]+$/;
const BANDWIDTH_VALUES = ['HIGH_bandwidth', 'LOW_bandwidth'] as const;

export async function GET(
    _req: Request,
    context: { params: { dataDir: string; bandwidth: string } }
) {
    const { dataDir, bandwidth } = await context.params;

    if (
        !DATA_DIR_REGEX.test(dataDir) ||
        !BANDWIDTH_VALUES.includes(bandwidth as any)
    ) {
        return NextResponse.json(
            { error: 'Invalid dataDir or bandwidth' },
            { status: 400 }
        );
    }

    const baseDir = path.resolve(
        process.cwd(),
        `../${dataDir}/output/${bandwidth}`
    );

    let entries: string[];
    try {
        entries = await readdir(baseDir);
    } catch {
        // missing or unreadable directory → empty list
        return NextResponse.json({ images: [] });
    }

    const checkFile = bandwidth === 'HIGH_bandwidth'
        ? 'annotated.jpg'
        : 'thumbnail.jpg';

    const images: string[] = [];
    for (const name of entries) {
        const dirPath = path.join(baseDir, name);
        try {
            const st = await stat(dirPath);
            if (!st.isDirectory()) continue;
            const candidate = path.join(dirPath, checkFile);
            const fstat = await stat(candidate);
            if (fstat.isFile()) {
                images.push(name);
            }
        } catch {
            // skip non-dirs or missing files
        }
    }

    return NextResponse.json({ images });
}
