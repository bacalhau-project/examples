import {useEffect, useState} from "react";

export interface OrchestratorNodesResponse {
    Nodes: Node[];
}

export interface Node {
    Info: Info;
    Membership: string;
    Connection: string;
    ConnectionState: ConnectionState;
}

export interface Info {
    NodeID: string;
    NodeType: string;
    Labels: Record<string, string>;
}

export interface ConnectionState {
    Status: string;
    LastHeartbeat: string;
    ConnectedSince: string;
    DisconnectedSince: string;
}



export function useSatellitesNodes(
    endpoint: string = 'http://localhost:8438/api/v1/orchestrator/nodes'
) {
    const [data, setData] = useState<OrchestratorNodesResponse["Nodes"] | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function fetchNodes() {
            setIsLoading(true);
            setError(null);

            try {
                const res = await fetch(endpoint);
                if (!res.ok) {
                    throw new Error(`HTTP error ${res.status}`);
                }
                const json: OrchestratorNodesResponse = await res.json();
                const computeOnly = json.Nodes.filter(
                    (n) => n.Info.NodeType === 'Compute'
                );
                if (!cancelled) {
                    setData(computeOnly);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err as Error);
                }
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        }

        fetchNodes();

        return () => {
            cancelled = true;
        };
    }, [endpoint]);

    return { data, isLoading, error };
}
