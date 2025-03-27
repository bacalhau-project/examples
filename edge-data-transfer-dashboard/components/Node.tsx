import {getStatusBadge, ProgressBar} from "@/components/NodesList";
import React from "react";
import {DisconnectButton} from "@/components/DisconnectButton";
import {NetworkLossButton} from "@/components/NetworkLostButton";
import {NodeProps} from "@/lib/JobProvider";

export const Node = ({node, color, jobs}: {node: NodeProps, color: string, jobs: any[]}) => {
    const nodeLabel = node.Info?.NodeID
    const idToCompare = nodeLabel === "Empty" ? "0" : nodeLabel;
    const count = jobs.filter((job) => job.nodeId === idToCompare).length;
    if(node.Info?.NodeType === 'Requester'){
        return null
    }

    return (
        <div key={nodeLabel} className="flex items-center p-2 rounded-md space-x-4">
            {/* Column 1: Color and Node Label */}
            <div className="flex items-center gap-2 w-60">
                <div className={`h-4 w-6 ${color}`} />
                <span className="truncate">
        {nodeLabel === "Empty" ? 'Files to process' : nodeLabel}
      </span>
            </div>

            {/* Column 2: Status */}
            <div className="w-32">
                {getStatusBadge(String(node?.ConnectionState?.Status).toLowerCase())}
            </div>

            {/* Column 3: Buttons */}
            <div className="flex items-center gap-2">
                <DisconnectButton
                    ip={node.Info.Labels.PUBLIC_IP}
                    isDisconnected={node.Connection === 'DISCONNECTED'}
                />
                <NetworkLossButton ip={node.Info.Labels.PUBLIC_IP} />
            </div>

            {/* Column 4: Progress Bar fills the remaining space */}
            <div className="flex-grow">
                <ProgressBar
                    nodeLabel={nodeLabel}
                    color={color}
                    count={count}
                    jobsLength={jobs.length}
                />
            </div>
        </div>
    );
}
