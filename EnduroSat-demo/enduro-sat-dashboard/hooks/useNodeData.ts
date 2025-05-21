import { useState, useEffect } from 'react';

export interface NodeData {
    modelName?: string;
    bandwidth?: string;
}

export function useNodeData(
    node: string,
    fields?: Array<'modelName' | 'bandwidth'>
) {
    const [data, setData] = useState<NodeData>({});
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!node) return;

        let isMounted = true;
        const params = new URLSearchParams({ node });
        if (fields && fields.length > 0) {
            params.set('fields', fields.join(','));
        }
        const url = `/api/node?${params.toString()}`;

        async function fetchData() {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(url);
                if (!res.ok) {
                    throw new Error(`Error ${res.status}: ${res.statusText}`);
                }
                const json: NodeData = await res.json();
                if (!isMounted) return;
                setData(json);
            } catch (err: any) {
                if (!isMounted) return;
                setError(err.message || 'Unknown error');
            } finally {
                if (isMounted) setLoading(false);
            }
        }

        fetchData();
        const intervalId = setInterval(fetchData, 3000);

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };
    }, [node, fields]);

    return { data, loading, error };
}
