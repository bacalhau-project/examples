import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import ReactFlow, {
  Controls,
  Background,
  useNodesState,
  ReactFlowProvider,
  Node as FlowNode,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { Message } from '@/page';
import { Badge } from '@/components/ui/badge';
import ClearQueueModal from '@/components/ClearQueueModal';
import Sidebar from '@/components/Sidebar';
import { NODE_SPACING, TOP_OFFSET } from '@/lib/constants';
import { CustomNode } from '@/components/CustomNode';
import { getContrastTextColor } from '@/lib/utils';
import { ModeToggle } from '@/components/ModeToggle';

export interface NodeData {
  vm_name: string;
  region: string;
  icon_name: string;
  label?: string;
  isUpdated?: boolean;
  color?: string;
}

interface Node extends FlowNode {
  data: NodeData;
}

function LabelNode({ data }: { data: { label: string; color: string } }) {
  return (
    <div
      className="flex items-center justify-center rounded-md px-3 py-1 font-bold"
      style={{
        backgroundColor: data.color,
        opacity: 0.9,
        color: getContrastTextColor(data.color),
      }}
    >
      {data.label}
    </div>
  );
}

interface NodeGraphProps {
  isConnected: boolean;
  setShowConfirm: (show: boolean) => void;
  clearQueue: () => void;
  vmStates: Map<string, Message>;
  queueSize: number;
  messageCount: number;
  lastPoll: string;
  showConfirm: boolean;
}

export default function NodeGraph({
  isConnected,
  setShowConfirm,
  clearQueue,
  vmStates,
  queueSize,
  messageCount,
  lastPoll,
  showConfirm,
}: NodeGraphProps) {
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [highlightedRegion, setHighlightedRegion] = useState(null);
  const [updatedNodes, setUpdatedNodes] = useState<Set<string>>(new Set());
  const prevVmStatesRef = useRef<Map<string, Message>>(new Map());

  // Detect changes in vmStates to track recently updated nodes
  useEffect(() => {
    const newUpdatedNodes = new Set<string>();

    vmStates.forEach((vm, vmName) => {
      const prevVm = prevVmStatesRef.current.get(vmName);
      // If VM is new or has changed data, mark it as updated
      if (!prevVm || JSON.stringify(prevVm) !== JSON.stringify(vm)) {
        newUpdatedNodes.add(vmName);
      }
    });

    prevVmStatesRef.current = new Map(vmStates);

    if (newUpdatedNodes.size > 0) {
      console.log('2');
      setUpdatedNodes(newUpdatedNodes);

      // Not the best way to do this, but it works for now

      // Clear the updated status after animation duration
      const timeoutId = setTimeout(() => {
        setUpdatedNodes(new Set());
      }, 500);

      return () => clearTimeout(timeoutId);
    }
  }, [vmStates]);

  const regions = Array.from(vmStates.values()).reduce((acc, vm) => {
    acc[vm.region] = vm.color;
    return acc;
  }, {});

  const nodes = Array.from(vmStates.values());

  return (
    <div className="fixed inset-0 overflow-hidden bg-white dark:bg-black">
      <div className="absolute inset-0">
        <ReactFlowProvider>
          <Flow
            nodes={nodes}
            onNodeSelect={setSelectedNode}
            highlightedRegion={highlightedRegion}
            updatedNodes={updatedNodes}
          />
        </ReactFlowProvider>
      </div>

      {/* Header floating on top */}
      <header className="bg-background/50 absolute top-0 right-0 left-0 z-10 backdrop-blur-md">
        <div className="flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">Network Visualization</h1>

            <Badge
              variant={isConnected ? 'default' : 'outline'}
              className={`${isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}
              onClick={() => setShowConfirm(true)}
            >
              {isConnected ? 'Connected' : 'Disconnected'}
            </Badge>
          </div>
          <div className="ml-auto flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm">Unique VMs:</span>
              <Badge>{vmStates.size}</Badge>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm">Queue Size:</span>
              <Badge>{queueSize}</Badge>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm">Messages Processed:</span>
              <Badge>{messageCount}</Badge>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm">Last Update:</span>
              <Badge>{lastPoll}</Badge>
            </div>
          </div>
        </div>
      </header>

      {/* Sidebar floating on top */}
      <aside className="absolute top-16 left-0 z-10 hidden w-[240px] p-4 md:block">
        <Sidebar
          highlightedRegion={highlightedRegion}
          setHighlightedRegion={setHighlightedRegion}
          regions={regions}
          selectedNode={selectedNode}
          setShowConfirm={setShowConfirm}
        />
      </aside>

      {/* Region legend floating at the bottom */}
      <div className="absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 transform flex-wrap justify-center gap-3 rounded-lg bg-black/50 px-4 py-2 backdrop-blur-xl">
        {Object.entries(regions).map(([region, color]) => (
          <div key={region} className="flex items-center gap-2">
            <div
              className="h-3 w-3 rounded-full"
              style={{ backgroundColor: color as string }}
            ></div>
            <span className="text-xs font-semibold text-gray-800 dark:text-white">{region}</span>
          </div>
        ))}

        {Object.keys(regions).length === 0 && (
          <span className="text-xs font-semibold text-gray-800 dark:text-white">No regions</span>
        )}
      </div>

      {/* Mode toggle floating at the bottom */}
      <div className="absolute right-4 bottom-4">
        <ModeToggle />
      </div>

      {/* Clear queue modal */}
      {showConfirm && <ClearQueueModal setShowConfirm={setShowConfirm} clearQueue={clearQueue} />}
    </div>
  );
}

function Flow({
  nodes,
  onNodeSelect,
  highlightedRegion,
  updatedNodes,
}: {
  nodes: Message[];
  onNodeSelect: (node: Node) => void;
  highlightedRegion: string | null;
  updatedNodes: Set<string>;
}) {
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([]);
  const nodeTypes = useMemo(
    () => ({
      custom: CustomNode,
      label: LabelNode,
    }),
    [],
  );

  const onNodeClick = useCallback(
    (_event, node) => {
      onNodeSelect(node);
    },
    [onNodeSelect],
  );

  useEffect(() => {
    const nodesByRegion = nodes.reduce<Record<string, Message[]>>((acc, node) => {
      if (!acc[node.region]) {
        acc[node.region] = [];
      }
      acc[node.region].push(node);
      return acc;
    }, {});

    const initialNodes = [];
    let currentX = 0;

    Object.entries(nodesByRegion).forEach(([region, regionNodes]) => {
      if (regionNodes.length === 0) return;

      // Calculate grid layout for this region's nodes
      const regionNodesCount = regionNodes.length;
      const rows = Math.ceil(Math.sqrt(regionNodesCount * 1.5));

      const regionColor = regionNodes[0].color;
      if (!highlightedRegion || region == highlightedRegion) {
        // Add a label node for this region
        initialNodes.push({
          id: `label-${region}`,
          type: 'label',
          data: {
            label: region,
            color: regionColor,
          },
          position: {
            x: currentX + (Math.ceil(regionNodesCount / rows) * NODE_SPACING) / 2 - 40, // Center the label
            y: TOP_OFFSET - 40, // Position above the region's nodes
          },
          draggable: false,
          selectable: false,
        });
      }

      regionNodes.forEach((vm, i) => {
        const col = Math.floor(i / rows);
        const row = i % rows;
        const shouldHide = highlightedRegion && vm.region !== highlightedRegion;
        const isUpdated = updatedNodes.has(vm.vm_name);

        initialNodes.push({
          id: vm.vm_name,
          type: 'custom',
          data: {
            ...vm,
            label: vm.vm_name,
            isUpdated, // Pass the update state to the custom node
          },
          position: {
            x: col * NODE_SPACING + currentX,
            y: row * NODE_SPACING + TOP_OFFSET,
          },
          style: shouldHide ? { display: 'none' } : {},
        });
      });

      // Update X position for next region (add padding between regions)
      const colsInRegion = Math.ceil(regionNodesCount / rows);
      currentX += colsInRegion * NODE_SPACING + NODE_SPACING; // Extra spacing between regions
    });

    setRfNodes(initialNodes);
  }, [nodes, setRfNodes, highlightedRegion, updatedNodes]);

  return (
    <ReactFlow
      attributionPosition="top-right"
      onNodeClick={onNodeClick}
      nodes={rfNodes}
      edges={[]}
      onNodesChange={onNodesChange}
      fitView
      nodeTypes={nodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      className="bg-gray-100 dark:bg-slate-900"
    >
      <Controls />
      <Background />
    </ReactFlow>
  );
}
