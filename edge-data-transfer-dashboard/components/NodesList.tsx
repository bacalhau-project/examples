"use client";

import {Card, CardContent, CardDescription, CardHeader, CardTitle} from "@/components/ui/card";
import {CheckCircle2, Database, RefreshCw, Slash, Wifi, WifiOff} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import React, {useMemo} from "react";
import {Node} from "./Node";
import {DisconnectButton} from "@/components/DisconnectButton";
import {NetworkLossButton} from "@/components/NetworkLostButton";
import {ClearMetadataButton} from "@/components/ClearMetadataButton";

export const getStatusBadge = (status) => {
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

// export default function useFetchNodes(setNodes, setLoading) {
//     useEffect(() => {
//         setLoading(true);
//
//         const fetchNodes = async () => {
//             const controller = new AbortController();
//             const timeoutId = setTimeout(() => controller.abort(), 5000);
//
//             try {
//                 const res = await fetch("/api/nodes", { signal: controller.signal });
//                 if (!res.ok) {
//                     throw new Error(`Failed to fetch data: ${res.status} ${res.statusText}`);
//                 }
//                 const data = await res.json();
//                 setNodes(data.output);
//             } catch (error) {
//                 if (error.name === "AbortError") {
//                     console.error("Request timed out");
//                 } else {
//                     console.error("Fetch error:", error.message);
//                 }
//             } finally {
//                 clearTimeout(timeoutId);
//                 setLoading(false);
//             }
//         };
//
//         fetchNodes();
//         const intervalId = setInterval(fetchNodes, 10000);
//
//         return () => clearInterval(intervalId);
//     }, [setNodes, setLoading]);
// }



export function NodesList({ nodes, filesLength = 0 }) {

    const filteredNodeIDs = useMemo(() => {
        return (
            nodes
                ?.filter((node) => node.Info.NodeType !== "Requester")
                .map((node) => node.Info.NodeID) ?? []
        );
    }, [nodes]);

    const nodeColorsMapping = useMemo(() => {
        const availableBorderColors = [
            "border-red-500",
            "border-blue-500",
            "border-green-500",
            "border-yellow-500",
            "border-gray-700",
        ];
        let mapping = { };
        filteredNodeIDs.forEach((nodeId, i) => {
            mapping[nodeId] = availableBorderColors[i % availableBorderColors.length];
        });
        return mapping;
    }, [filteredNodeIDs]);
    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle>Environment Setup</CardTitle>
                <CardDescription>Edge nodes configuration</CardDescription>
                <ClearMetadataButton nodes={nodes} />
            </CardHeader>
            <CardContent>
                <div className="space-y-4 w-full">
                            <div className="text-sm font-medium">Source Nodes</div>
                                {nodes?.map((node) => {
                                    if (node.Info.NodeType === "Requester") return null;
                                    return (
                                        <div className="flex flex-row gap-1 justify-center items-center" key={node.Info.NodeID}>
                                            <DisconnectButton node={node}/>
                                            <NetworkLossButton node={node}/>
                                            <div className="flex-1">
                                                <Node node={node} color={nodeColorsMapping[node.Info.NodeID]}/>
                                            </div>
                                        </div>
                                    );
                                })}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-2 gap-4">
                    <div className="flex flex-col gap-2 mt-4">
                        <div className="text-sm font-medium">Destination Node</div>
                        <div className="flex items-center justify-between p-2 border rounded-md">
                            <div className="flex items-center gap-2">
                                <Database className="h-4 w-4 text-muted-foreground"/>
                                <span>Destination Node</span>
                            </div>
                            <Badge variant="outline" className="bg-blue-100 text-blue-800">
                                <Wifi className="h-3 w-3 mr-1"/> Online
                            </Badge>
                        </div>
                    </div>
                    {/*<div className="flex flex-col gap-2">*/}
                    {/*    <div className="mt-4">*/}
                    {/*        <div className="text-sm font-medium mb-2">Network Share</div>*/}
                    {/*        <div className="flex items-center justify-between p-2 border rounded-md">*/}
                    {/*            <div className="flex items-center gap-2">*/}
                    {/*                <HardDrive className="h-4 w-4 text-muted-foreground"/>*/}
                    {/*                <span>NFS Share</span>*/}
                    {/*            </div>*/}
                    {/*            <div className="text-sm text-muted-foreground">{filesLength}</div>*/}
                    {/*        </div>*/}
                    {/*    </div>*/}
                    {/*</div>*/}
                </div>
            </CardContent>
        </Card>
    );
}
