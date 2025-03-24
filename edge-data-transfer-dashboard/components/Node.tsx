import {Server} from "lucide-react";
import {getStatusBadge} from "@/components/NodesList";



export const Node = ({node}) => {
    if(node.Info.NodeType === 'Requester'){
        return null
    }
    return (
        <div key={node.Info.NodeID} className="flex items-center justify-between p-2 border rounded-md">
        <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-muted-foreground"/>
            <span>{node.Info.NodeID.substring(0, 27)}...</span>
        </div>
        {getStatusBadge(
            String(node?.ConnectionState.Status).toLowerCase()
        )}
    </div>
    )
}
