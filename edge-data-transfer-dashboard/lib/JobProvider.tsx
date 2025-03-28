import {createContext, ReactNode, useContext, useEffect, useMemo, useState} from "react";
import {useNodes} from "@/lib/NodeProvider";
import {useFetchFiles} from "@/hooks/useFetchFiles";


export interface NodeProps {
    Info: {
        NodeID: string;
        NodeType: string;
        Labels: {
            PUBLIC_IP: string;
        };
    };
    Connection: string,
    ConnectionState: {
        Status: string
    }
}

const useNodeMetaData = (nodes: NodeProps[]) => {
    const [metaData, setMetaData] = useState<{ [key: string]: string[] }>({});

    useEffect(() => {
        if (!nodes || nodes.length === 0) return;

        const fetchAllNodeMetaFiles = async () => {
            const metaDataAggregate: { [key: string]: string[] } = {};
            await Promise.all(
                nodes.map(async (node) => {
                    const {
                        Info: { NodeID, Labels: { PUBLIC_IP } },
                    } = node;
                    if (PUBLIC_IP) {
                        const controller = new AbortController();
                        const timeoutId = setTimeout(() => controller.abort(), 3000);

                        try {
                            const response = await fetch(`http://${PUBLIC_IP}:9123/process_file`, {
                                method: "GET",
                                headers: {
                                    "Content-Type": "application/json",
                                    Authorization: `Bearer abrakadabra1234!@#`,
                                },
                                signal: controller.signal,
                            });
                            clearTimeout(timeoutId);
                            if (!response.ok) {
                                throw new Error(`Error fetching data from node ${NodeID}`);
                            }
                            const data = await response.json();
                            metaDataAggregate[NodeID] = data.files;
                        } catch (error: any) {
                            if (error.name === "AbortError") {
                                console.warn(`Request to node ${NodeID} aborted due to timeout.`);
                            } else {
                                // console.error("Error fetching metadata for node", NodeID, error);
                            }
                        }
                    }
                })
            );
            setMetaData(metaDataAggregate);
        };

        fetchAllNodeMetaFiles();
        const intervalId = setInterval(fetchAllNodeMetaFiles, 2000);
        return () => clearInterval(intervalId);
    }, [nodes]);

    return metaData;
};

interface JobsContextProps {
    jobs: any[];
    files: string[];
    nodeColorsMapping: { [key: string]: string };
}
const JobsContext = createContext<JobsContextProps | undefined>(undefined);

export const JobsProvider = ({children}: {children: ReactNode}) => {
    const {nodes, filteredNodeIDs, nodeColorsMapping} = useNodes()
    const files = useFetchFiles(nodes)
    const metaData = useNodeMetaData(nodes);

    const jobs = useMemo(() => {
        return files.map((file, index) => {
            let jobNodeId = "0";
            Object.entries(metaData).forEach(([nodeId, processedFiles]) => {
                if (processedFiles.some((metaFile) => metaFile.startsWith(`${file}.`))) {
                    jobNodeId = nodeId;
                }
            });
            const metaInvalid = jobNodeId !== "0" && !filteredNodeIDs.includes(jobNodeId);
            return {
                id: index + 1,
                fileName: file,
                nodeId: jobNodeId,
                metaInvalid,
            };
        });
    }, [files, metaData, filteredNodeIDs]);

    const value: JobsContextProps = {jobs, files, nodeColorsMapping}

    return (
        <JobsContext.Provider value={value}>
            {children}
        </JobsContext.Provider>
    )
}

export const useJobs = (): JobsContextProps => {
    const context = useContext(JobsContext);
    if (context === undefined) {
        throw new Error('useJobs has to be used with JobsProvider');
    }
    return context;
}
