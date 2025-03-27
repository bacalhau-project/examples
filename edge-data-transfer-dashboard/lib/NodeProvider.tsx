import {createContext, ReactNode, useContext, useMemo} from "react";
import useFetchNodes from "@/hooks/useFetchNodes";
import {NodeProps} from "@/lib/JobProvider";

interface NodeContextProps {
    nodes: NodeProps[];
    filteredNodeIDs: string[];
    nodeColorsMapping: { [key: string]: string };
}
const NodeContext = createContext<NodeContextProps | undefined>(undefined);

export const NodeProvider = ({children}: {children: ReactNode}) => {
    const {nodes} = useFetchNodes()

    const filteredNodeIDs = useMemo(() => {
        return (
            nodes
                ?.filter((node) => node.Info.NodeType !== "Requester")
                .map((node) => node.Info.NodeID) ?? []
        );
    }, [nodes]);

    const nodeColorsMapping = useMemo(() => {
        const availableColors = [
            "bg-red-500",
            "bg-blue-500",
            "bg-green-500",
            "bg-yellow-500",
            "bg-gray-700",
        ];
        let mapping: { [key: string]: string } = { "0": "bg-white" };
        filteredNodeIDs.forEach((nodeId, i) => {
            mapping[nodeId] = availableColors[i % availableColors.length];
        });
        return mapping;
    }, [filteredNodeIDs]);

    const value: NodeContextProps = {nodes, nodeColorsMapping, filteredNodeIDs}

    return (
        <NodeContext.Provider value={value}>
            {children}
        </NodeContext.Provider>
    )
}

export const useNodes = (): NodeContextProps => {
    const context = useContext(NodeContext);
    if (context === undefined) {
        throw new Error('useNodes has to be used with NodeProvider');
    }
    return context;
}
