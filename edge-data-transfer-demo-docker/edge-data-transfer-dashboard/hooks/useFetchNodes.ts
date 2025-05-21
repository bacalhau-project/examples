"use client";

import { useEffect, useState, useCallback } from "react";

export default function useFetchNodes() {
    const [nodes, setNodes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchNodes = useCallback(async (signal) => {
        try {
            const res = await fetch("/api/nodes", { signal });
            if (!res.ok) throw new Error(`HTTP ${res.status} - ${res.statusText}`);
            const data = await res.json();
            return data.output;
        } catch (error) {
            if (!signal.aborted) setError(error.message);
            return null;
        }
    }, []);

    useEffect(() => {
        const updateNodes = async () => {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000);
            setLoading(true);
            const newNodes = await fetchNodes(controller.signal);
            clearTimeout(timeoutId);
            if (newNodes) {
                setNodes(prev => {
                    const prevString = JSON.stringify(prev);
                    const newString = JSON.stringify(newNodes);
                    return prevString === newString ? prev : newNodes;
                });
            }
            setLoading(false);
        };

        updateNodes();
        const intervalId = setInterval(updateNodes, 5000);

        return () => {
            clearInterval(intervalId);
        };
    }, [fetchNodes]);

    return { nodes, loading, error };
}
