// app/api/node/route.ts
import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const node = searchParams.get('node');
    const fieldsParam = searchParams.get('fields');

    if (!node || !/^node[1-5]$/.test(node)) {
        return NextResponse.json(
            { error: 'Invalid node parameter. Must be one of node1–node5.' },
            { status: 400 }
        );
    }

    const projectRoot = process.cwd();
    const modelFile = path.join(projectRoot, '..', `app/model-${node}.txt`);
    const bandwidthFile = path.join(
        projectRoot,
        '..',
        `${node}-data`,
        'config',
        'bandwidth.txt'
    );

    let modelName = 'Yolo';
    let bandwidth = 'LOW';

    try {
        const modelRaw = await fs.readFile(modelFile, 'utf8');
        modelName = modelRaw.trim();
        if (modelName.toLowerCase().endsWith('.pt')) {
            modelName = modelName.slice(0, -3);
        }
    } catch (err: any) {
        if (err.code !== 'ENOENT') {
            console.error('Error reading model file:', err);
            return NextResponse.json(
                { error: 'Failed to read model file.' },
                { status: 500 }
            );
        }
    }

    try {
        const bandwidthRaw = await fs.readFile(bandwidthFile, 'utf8');
        bandwidth = bandwidthRaw.trim();
    } catch (err: any) {
        if (err.code !== 'ENOENT') {
            console.error('Error reading bandwidth file:', err);
            return NextResponse.json(
                { error: 'Failed to read bandwidth file.' },
                { status: 500 }
            );
        }
    }

    const allowedFields = ['modelName', 'bandwidth'] as const;
    const result: Record<string, string> = {};

    if (fieldsParam) {
        const requested = fieldsParam
            .split(',')
            .map(f => f.trim())
            .filter(f => allowedFields.includes(f as typeof allowedFields[number]));

        if (requested.length === 0) {
            return NextResponse.json(
                { error: 'Invalid fields parameter. Must include modelName and/or bandwidth.' },
                { status: 400 }
            );
        }

        if (requested.includes('modelName')) result.modelName = modelName;
        if (requested.includes('bandwidth')) result.bandwidth = bandwidth;
    } else {
        result.modelName = modelName;
        result.bandwidth = bandwidth;
    }

    return NextResponse.json(result);
}
