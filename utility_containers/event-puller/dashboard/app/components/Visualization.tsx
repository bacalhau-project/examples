import { Message } from '../page';
import VMTable from './VMTable';
import { columns } from './VMTableColumns';

interface VisualizationProps {
  vmStates: Map<string, Message>;
}

export default function Visualization({ vmStates }: Readonly<VisualizationProps>) {
  return (
    <div className="flex-1 p-4">
      <div className="bg-white p-4 shadow-md">
        <h2 className="mb-4 text-lg font-bold">Event Visualization</h2>
        <VMTable columns={columns()} data={Array.from(vmStates.values())} />
      </div>
    </div>
  );
}
