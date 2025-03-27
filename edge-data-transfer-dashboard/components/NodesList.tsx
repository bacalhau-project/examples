"use client";

import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import {CheckCircle2, HardDrive, RefreshCw, Slash, Wifi, WifiOff} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import React from "react";
import {Node} from "./Node";
import {useNodes} from "@/lib/NodeProvider";
import {useJobs} from "@/lib/JobProvider";

export const getStatusBadge = (status: string) => {
    switch (status) {
        case "connected":
            return (
                <Badge variant="outline" className="bg-green-100 text-green-800">
                    <Wifi className="h-3 w-3 mr-1" /> Connected
                </Badge>
            );
        case "running":
            return (
                <Badge variant="outline" className="bg-blue-100 text-blue-800">
                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" /> Running
                </Badge>
            );
        case "completed":
            return (
                <Badge variant="outline" className="bg-green-100 text-green-800">
                    <CheckCircle2 className="h-3 w-3 mr-1" /> Completed
                </Badge>
            );
        case "disconnected":
            return (
                <Badge variant="outline" className="bg-red-100 text-red-800">
                    <Slash className="h-3 w-3 mr-1" /> Disconnected
                </Badge>
            );
        case "network-loss":
            return (
                <Badge variant="outline" className="bg-yellow-100 text-yellow-800">
                    <WifiOff className="h-3 w-3 mr-1" /> Network Loss
                </Badge>
            );
        default:
            return <Badge variant="outline">Unknown</Badge>;
    }
};

export const FilesProgressBar = ({count, jobsLength} : { count: number, jobsLength: number}) => {
    const progress = jobsLength > 0 ? ((jobsLength - count) / jobsLength) * 100 : 100;
    return (
        <div className="flex items-center gap-2 w-full ml-10">
            <div className="h-2 w-full rounded-full bg-muted">
                <div
                    className={`h-2 rounded-full bg-gray-400`}
                    style={{width: `${progress}%`}}
                />
            </div>
            <span className="text-sm text-muted-foreground">
        {count} files to process ({progress.toFixed(1)}%)
      </span>
        </div>
    )
}

export const ProgressBar = ({nodeLabel, color, count, jobsLength} : {nodeLabel: string, color: string, count: number, jobsLength: number}) => {
    const expectedPerNode = jobsLength * 0.2;
    let progress: number;

    if (nodeLabel === "Empty") {
        progress = count === 0 ? 100 : 0;
    } else {
        progress = expectedPerNode > 0 ? (count / expectedPerNode) * 100 : 0;
        if (progress > 100) progress = 100;
    }

    return (
        <div className="flex items-center gap-2">
            <div className="h-2 w-full max-w-md rounded-full bg-muted">
                <div
                    className={`h-2 rounded-full ${color}`}
                    style={{ width: `${progress}%` }}
                />
            </div>
            <span className="text-sm text-muted-foreground">
        {count} files ({progress.toFixed(1)}%)
      </span>
        </div>
    );
};

export function NodesList() {
    const {nodeColorsMapping, nodes} = useNodes()
    const {jobs, files} = useJobs()

    return (
        <Card>
            <CardHeader className="pb-1">
                <div className="flex items-center justify-between w-full">
                    <div className="text-lg font-bold">Source Nodes</div>
                    <div className={"flex-1 flex justify-end"}>
                        <FilesProgressBar count={jobs.filter((job) => job.nodeId === "0").length } jobsLength={jobs.length}/>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-1 w-full">
                    {nodes?.map((node) => {
                        if (node.Info?.NodeType === "Requester") return null;
                        return (
                            <div className="flex flex-row gap-1 justify-center items-center" key={node.Info?.NodeID}>
                                <div className="flex-1">
                                    <Node node={node} color={nodeColorsMapping[node.Info?.NodeID] ?? 'bg-black'} jobs={jobs}/>
                                </div>
                            </div>
                                    );
                                })}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-2 gap-4">
                    {/*<div className="flex flex-col gap-2 mt-4">*/}
                    {/*    <div className="text-sm font-medium">Destination Node</div>*/}
                    {/*    <div className="flex items-center justify-between p-2 border rounded-md">*/}
                    {/*        <div className="flex items-center gap-2">*/}
                    {/*            <Database className="h-4 w-4 text-muted-foreground"/>*/}
                    {/*            <span>Destination Node</span>*/}
                    {/*        </div>*/}
                    {/*        <Badge variant="outline" className="bg-blue-100 text-blue-800">*/}
                    {/*            <Wifi className="h-3 w-3 mr-1"/> Online*/}
                    {/*        </Badge>*/}
                    {/*    </div>*/}
                    {/*</div>*/}

                </div>
            </CardContent>
        </Card>
    );
}
