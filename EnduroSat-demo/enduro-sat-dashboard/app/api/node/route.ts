import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const NODE_REGEX = /^node[1-5]$/;
const DEFAULT_MODEL = 'Yolo';

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const node = searchParams.get('node');
    const fieldsParam = searchParams.get('fields');

    if (!node || !NODE_REGEX.test(node)) {
        return NextResponse.json(
            { error: 'Invalid node parameter. Must be one of node1–node5.' },
            { status: 400 }
        );
    }

    const modelFile = path.join('/app/models', `model-${node}.txt`);
    const bandwidthFile = path.join(
        '/app/data',
        `${node}-data`,
        'config',
        'bandwidth.txt'
    );

    let modelName = DEFAULT_MODEL;
    try {
        const raw = await fs.readFile(modelFile, 'utf8');
        modelName = raw.trim().replace(/\.pt$/i, '');
    } catch (err: any) {
        if (err.code !== 'ENOENT') {
            console.error(err);
            return NextResponse.json(
                { error: 'Failed to read model file.' },
                { status: 500 }
            );
        }
    }

    let bandwidth = 'LOW';
    try {
        const raw = await fs.readFile(bandwidthFile, 'utf8');
        bandwidth = raw.trim();
    } catch (err: any) {
        if (err.code !== 'ENOENT') {
            console.error(err);
            return NextResponse.json(
                { error: 'Failed to read bandwidth file.' },
                { status: 500 }
            );
        }
    }

    const allowed = ['modelName', 'bandwidth'] as const;
    const result: Record<string, string> = {};

    if (fieldsParam) {
        const req = fieldsParam
            .split(',')
            .map(f => f.trim())
            .filter(f => allowed.includes(f as typeof allowed[number]));
        if (req.length === 0) {
            return NextResponse.json(
                { error: 'Invalid fields parameter.' },
                { status: 400 }
            );
        }
        if (req.includes('modelName')) result.modelName = modelName;
        if (req.includes('bandwidth')) result.bandwidth = bandwidth;
    } else {
        result.modelName = modelName;
        result.bandwidth = bandwidth;
    }

    return NextResponse.json(result);
}
