'use client'
import {Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle} from "@/components/ui/card";
import {Progress} from "@/components/ui/progress";
import {FileJson} from "lucide-react";
import {getStatusBadge} from "@/components/NodesList";
import {useEffect, useState} from "react";

export const Transfer = ({nodes, progress, jobRunning}) => {
    const [nodesFiles, setNodesFiles] = useState({ Node1: [], Node2: [], Node3: [], Node4: [], Node5: [] });

    useEffect(() => {
        const fetchNodesFiles = async () => {
            try {
                const response = await fetch('/api/proces');
                if (!response.ok) {
                    throw new Error('Error when fetching data');
                }
                const data = await response.json();
                setNodesFiles(data);
            } catch (error) {
                console.error('Error:', error);
            }
        };

        fetchNodesFiles();
        const intervalId = setInterval(fetchNodesFiles, 10000);
        return () => clearInterval(intervalId);
    }, [jobRunning]);

    return (<Card>
        <CardHeader className="pb-2">
            <CardTitle>Transfer Status</CardTitle>
            <CardDescription>Overall job progress</CardDescription>
        </CardHeader>
        <CardContent>
            <div className="space-y-4">
                <div className="flex flex-col gap-1">
                    <div className="flex justify-between text-sm">
                        <span>Overall Progress</span>
                        {/*<span>{Math.round(progress.overall)}%</span>*/}
                    </div>
                    {/*<Progress value={progress.overall} className="h-2" />*/}
                </div>

                <div className="grid gap-3">
                    {nodes?.map((node, i) => {
                        const nodeKey = node.Info.NodeID + i
                        const nodeProgress = progress[nodeKey]
                        const status = String(node?.ConnectionState.Status).toLowerCase()
                        if(i == 0) {
                            return null
                        }
                        return (
                            <div key={nodeKey} className="space-y-1">
                                <div className="flex justify-between text-sm">
                                    <div className="flex items-center gap-1">
                                        <span>{node.Info.NodeID}</span>
                                        {getStatusBadge(status)}
                                    </div>
                                    <span>{Math.round(nodeProgress)}%</span>
                                </div>
                                <Progress value={nodeProgress} className="h-1.5" />
                                <div className="text-xs text-muted-foreground">
                                    {status === "running" && `Processing files ${i + 1}, ${i + 6}, ${i + 11}...`}
                                    {status === "completed" && "200 files processed successfully"}
                                    {status === "disconnected" && "Node disconnected from controller"}
                                    {status === "network-loss" && "Network connection to destination lost"}
                                    {status === "connected" && "Waiting to start..."}
                                </div>
                            </div>
                        )
                    })}
                </div>
            </div>
        </CardContent>
        <CardFooter>
            <div className="text-sm text-muted-foreground flex items-center gap-1">
                <FileJson className="h-4 w-4" />
                <span>Metadata files processed: {jobRunning ? Math.round(progress.overall * 10) : 0}/1000</span>
            </div>
        </CardFooter>
    </Card>)
}
