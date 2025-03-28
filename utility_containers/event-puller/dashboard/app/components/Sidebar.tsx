import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { getContrastTextColor } from '../lib/utils';
import { Node as FlowNode } from 'reactflow';
import { NodeData } from '@/NodeGraph';

interface Node extends FlowNode {
  data: NodeData;
}

interface SidebarProps {
  highlightedRegion: string | null;
  setHighlightedRegion: (region: string | null) => void;
  regions: Record<string, string>;
  selectedNode: Node | null;
  setOpenClearQueue: (show: boolean) => void;
}

export default function Sidebar({
  highlightedRegion,
  setHighlightedRegion,
  regions,
  selectedNode,
  setOpenClearQueue,
}: SidebarProps) {
  return (
    <>
      <Card className="bg-background/50 p-4 backdrop-blur-md">
        <div>
          <h3 className="mb-2 text-sm font-medium">Filter by Region</h3>
          <div className="grid grid-cols-1 gap-2">
            <Badge
              variant={!highlightedRegion ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => setHighlightedRegion(null)}
            >
              All Regions
            </Badge>
            {Object.entries(regions).map(([region, color]) => (
              <Badge
                key={region}
                variant={highlightedRegion === region ? 'default' : 'outline'}
                className="cursor-pointer"
                style={{
                  backgroundColor: highlightedRegion === region ? (color as string) : 'transparent',
                  color:
                    highlightedRegion === region
                      ? getContrastTextColor(color as string)
                      : 'inherit',
                }}
                onClick={() => setHighlightedRegion(region)}
              >
                {region}
              </Badge>
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-2 text-sm font-medium">Actions</h3>
          <Button
            size="sm"
            className="cursor-pointer"
            variant="destructive"
            onClick={() => setOpenClearQueue(true)}
          >
            Clear Queue
          </Button>
        </div>
      </Card>

      {selectedNode && (
        <Card className="bg-background/80 mt-4 p-4 backdrop-blur">
          <h2 className="mb-2 text-lg font-semibold">Node Details</h2>
          <div className="space-y-2">
            <div>
              <span className="text-sm font-medium">Name:</span>
              <span className="ml-2 text-sm">{selectedNode.data.hostname}</span>
            </div>
            <div>
              <span className="text-sm font-medium">Region:</span>
              <span className="ml-2 text-sm">{selectedNode.data.region}</span>
            </div>
            <div className="flex items-center">
              <span className="text-sm font-medium">Icon:</span>
              <span className="ml-2">{selectedNode.data.icon_name}</span>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
