import {NextResponse} from "next/server";

interface NodesFiles {
    Node1: string[];
    Node2: string[];
    Node3: string[];
    Node4: string[];
    Node5: string[];
}

export async function GET() {
    try {
        const externalRes = await fetch('http://51.20.252.232:9123/process_file', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer abrakadabra1234!@#`,
            },
        });
        if (!externalRes.ok) {
            throw new Error('Error');
        }

        const files: {files: string[]} = await externalRes.json();
        return NextResponse.json(files);
        const nodes: NodesFiles = {
            Node1: [],
            Node2: [],
            Node3: [],
            Node4: [],
            Node5: [],
        };

        files.files.forEach((file, index) => {
            const nodeNumber = (index % 5) + 1;
            const key = `Node${nodeNumber}` as keyof NodesFiles;
            nodes[key].push(file);
        });

        return NextResponse.json(nodes);
    } catch (error) {
        return NextResponse.json({error: error instanceof Error ? error.message : 'Error'});
    }
}
