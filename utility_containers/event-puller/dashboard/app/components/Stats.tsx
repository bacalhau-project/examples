import { Message } from '../page';

interface StatsProps {
  vmStates: Map<string, Message>;
  queueSize: number;
  messageCount: number;
  lastPoll: string;
}

export default function Stats({ vmStates, queueSize, messageCount, lastPoll }: StatsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-4">
      <div className="rounded bg-white p-4 shadow-md">
        <div className="mb-1 text-sm text-gray-500">Unique VMs</div>
        <div className="text-2xl font-bold">{vmStates.size}</div>
      </div>
      <div className="rounded bg-white p-4 shadow-md">
        <div className="mb-1 text-sm text-gray-500">Queue Size</div>
        <div className="text-2xl font-bold">{queueSize}</div>
      </div>
      <div className="rounded bg-white p-4 shadow-md">
        <div className="mb-1 text-sm text-gray-500">Messages Processed</div>
        <div className="text-2xl font-bold">{messageCount}</div>
      </div>
      <div className="rounded bg-white p-4 shadow-md">
        <div className="mb-1 text-sm text-gray-500">Last Update</div>
        <div className="text-2xl font-bold">{lastPoll}</div>
      </div>
    </div>
  );
}
