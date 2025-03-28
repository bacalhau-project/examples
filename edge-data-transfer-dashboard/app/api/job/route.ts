import { exec } from 'child_process';
import { NextResponse } from 'next/server';

export async function POST() {
    return new Promise((resolve) => {
        const child = exec('bacalhau job run job.yaml --id-only');

        child.stdout.on('data', (data) => {
            if (data) {
                console.log('stdout:', data);
                child.kill('SIGINT');
                resolve(NextResponse.json({ message: data }));
            }
        });

        child.stderr.on('data', (data) => {
            console.error('stderr:', data);
        });

        child.on('error', (error) => {
            resolve(NextResponse.json({ error: error.message }, { status: 500 }));
        });

        child.on('close', (code) => {
            if (code !== 0) {
                resolve(NextResponse.json({ error: `Process exited with code ${code}` }));
            }
        });
    });
}
