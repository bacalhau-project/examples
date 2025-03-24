"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";

interface Job {
    id: number;
    fileName: string;
    nodeId: string; // "0" means empty; otherwise the real NodeID from backend
    metaInvalid?: boolean;
}

interface Node {
    Info: {
        NodeID: string;
        NodeType: string;
        Labels: {
            PUBLIC_IP: string;
        };
    };
}

// Custom hook to fetch metadata from nodes.
const useNodeMetaData = (nodes: Node[], jobRunning: boolean) => {
    const [metaData, setMetaData] = useState<{ [key: string]: string[] }>({});

    useEffect(() => {
        if (!nodes || nodes.length === 0) return;

        const fetchAllNodeMetaFiles = async () => {
            try {
                const metaDataAggregate: { [key: string]: string[] } = {};
                await Promise.all(
                    nodes.map(async (node) => {
                        try {
                            const {
                                Info: {NodeID, Labels: {PUBLIC_IP}},
                            } = node;
                            // Adjust the URL and port as needed.
                            if (PUBLIC_IP) {
                                const response = await fetch(`http://${PUBLIC_IP}:9123/process_file`, {
                                    method: "GET",
                                    headers: {
                                        "Content-Type": "application/json",
                                        Authorization: `Bearer abrakadabra1234!@#`,
                                    },
                                });
                                if (!response.ok) {
                                    throw new Error(`Error fetching data from node ${NodeID}`);
                                }
                                const data = await response.json();
                                // Assume data.files is an array of processed file names for this node.
                                metaDataAggregate[NodeID] = data.files;
                            }
                        }
                        catch
                            (error: any)
                            {
                                if (error.name === "AbortError") return; // Ignore abort errors
                                console.error("Error fetching metadata for node", node.Info.NodeID, error);
                            }

                    })
                );
                setMetaData(metaDataAggregate);
            } catch (error) {
                console.error("Error aggregating metadata:", error);
            }
        };

        fetchAllNodeMetaFiles();
        const intervalId = setInterval(fetchAllNodeMetaFiles, 1000);
        return () => clearInterval(intervalId);
    }, [nodes]);

    return metaData;
}

const FilesGrid = React.memo(function FilesGrid({
                                                    nodes,
                                                    files,
                                                }: {
    nodes: Node[];
    files: string[];
}) {
    // 1. Build a list of real node IDs (exclude "Requester")
    const filteredNodeIDs = useMemo(() => {
        return (
            nodes
                ?.filter((node) => node.Info.NodeType !== "Requester")
                .map((node) => node.Info.NodeID) ?? []
        );
    }, [nodes]);

    // 2. Build a mapping from node ID (string) to a color.
    // "0" represents empty.
    const nodeColorsMapping = useMemo(() => {
        const availableColors = [
            "bg-red-500",
            "bg-blue-500",
            "bg-green-500",
            "bg-yellow-500",
            "bg-purple-500",
        ];
        let mapping: { [key: string]: string } = { "0": "bg-gray-200" };
        filteredNodeIDs.forEach((nodeId, i) => {
            mapping[nodeId] = availableColors[i % availableColors.length];
        });
        return mapping;
    }, [filteredNodeIDs]);

    // 3. Build a memoized list for legends and stats: first element is "Empty", then real node IDs.
    const memoizedNodes = useMemo(() => {
        return ["Empty", ...filteredNodeIDs];
    }, [filteredNodeIDs]);

    // 4. Fetch metadata from each node’s endpoint using the custom hook.
    const metaData = useNodeMetaData(nodes);

    // 5. Build jobs based on files and metadata.
    // For each file, we check if it exists in one of the node's metadata.
    // If yes, we assign that real node id; otherwise, the job remains "0" (empty).
    // If metadata exists for a file but the node id is not in our filtered list, mark it as invalid.
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

    // -----------------------------
    // Legend Component
    // -----------------------------
    const Legend = React.memo(({ nodesList }: { nodesList: string[] }) => {
        return (
            <div className="flex flex-wrap gap-4">
                {nodesList.map((nodeLabel) => (
                    <div key={nodeLabel} className="flex items-center gap-2">
                        <div className={`h-4 w-4 ${nodeColorsMapping[nodeLabel === "Empty" ? "0" : nodeLabel]}`} />
                        <span>{nodeLabel}</span>
                    </div>
                ))}
            </div>
        );
    });

    // -----------------------------
    // JobGrid Component
    // -----------------------------
    const JobGrid = React.memo(({ jobs, nodesList }: { jobs: Job[]; nodesList: string[] }) => {
        return (
            <TooltipProvider>
                <div className="grid grid-cols-[repeat(auto-fill,minmax(16px,1fr))] gap-1">
                    {jobs.map((job) => (
                        <Tooltip key={job.id}>
                            <TooltipTrigger asChild>
                                <div
                                    className={`h-4 w-4 ${nodeColorsMapping[job.nodeId]} ${
                                        job.metaInvalid ? "border border-blue-500" : ""
                                    } cursor-pointer transition-transform hover:scale-150`}
                                />
                            </TooltipTrigger>
                            <TooltipContent side="top">
                                    <p>{job.fileName}</p>
                            </TooltipContent>
                        </Tooltip>
                    ))}
                </div>
            </TooltipProvider>
        );
    });

    // -----------------------------
    // Stats Component
    // -----------------------------
    const Stats = React.memo(({ jobs, nodesList }: { jobs: Job[]; nodesList: string[] }) => {
        const expectedPerNode = jobs.length * 0.2;

        return (
            <div className="rounded-lg border p-4">
                <h3 className="mb-2 font-medium">Job Distribution Statistics</h3>
                <div className="space-y-2">
                    {nodesList.map((nodeLabel) => {
                        const idToCompare = nodeLabel === "Empty" ? "0" : nodeLabel;
                        const count = jobs.filter((job) => job.nodeId === idToCompare).length;

                        let progress: number;
                        if (nodeLabel === "Empty") {
                            // For "Empty": if there are no jobs, the progress is 100%, otherwise 0.
                            progress = count === 0 ? 100 : 0;
                        } else {
                            // For other nodes, calculate the progress based on the ratio of actual jobs to expected jobs.
                            progress = expectedPerNode > 0 ? (count / expectedPerNode) * 100 : 0;
                            if (progress > 100) progress = 100;
                        }

                        return (
                            <div key={nodeLabel} className="flex items-center gap-2">
                                <div className={`h-3 w-3 ${nodeColorsMapping[nodeLabel === "Empty" ? "0" : nodeLabel]}`} />
                                <span className="min-w-[80px]">{nodeLabel}:</span>
                                <div className="h-2 w-full max-w-md rounded-full bg-muted">
                                    <div
                                        className={`h-2 rounded-full ${nodeColorsMapping[nodeLabel === "Empty" ? "0" : nodeLabel]}`}
                                        style={{ width: `${progress}%` }}
                                    />
                                </div>
                                <span className="text-sm text-muted-foreground">
                                {count} jobs ({progress.toFixed(1)}%)
                            </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    });

    return (
        <div className="space-y-6 p-4">
            <JobGrid jobs={jobs} nodesList={memoizedNodes} />
            <Stats jobs={jobs} nodesList={memoizedNodes} />
        </div>
    );
});

export default FilesGrid;
