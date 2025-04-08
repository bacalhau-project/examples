import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { access } from 'fs/promises';
import { promisify } from 'util';
import { constants } from 'fs';

const execPromise = promisify(exec);

export async function GET() {
    try {
        let command = 'bacalhau node list --output json';
        try {
            await access('config.yaml', constants.F_OK);
            command = 'bacalhau node list --config config.yaml --output json';
        } catch {}
        const { stdout } = await execPromise(command);
        return NextResponse.json({ output: JSON.parse(stdout) });
    } catch (error) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
