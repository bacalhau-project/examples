import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execPromise = promisify(exec);

export async function GET() {
    try {
        const { stdout } = await execPromise('bacalhau node list --output json');
        return NextResponse.json({ output: JSON.parse(stdout) });
    } catch (error) {
        return NextResponse.json({ error: error.message }, { status: 500 });
    }
}
