import { Message } from '@/page';

interface CustomNodeProps {
  data: Message & {
    isUpdated: boolean;
    label: string;
  };
}

export function CustomNode({ data }: CustomNodeProps) {
  return (
    <div
      className={`relative flex cursor-pointer items-center justify-center rounded-full ${data.isUpdated ? 'animate-pulse' : ''}`}
      style={{
        width: `38px`,
        height: `38px`,
        backgroundColor: data.color,
      }}
    >
      <div
        className="absolute flex items-center justify-center rounded-full"
        style={{
          width: `${data.isUpdated ? 0 : 32}px`,
          height: `${data.isUpdated ? 0 : 32}px`,
          backgroundColor: data.color,
        }}
      >
        <span className="text-xl">{data.icon_name}</span>
      </div>
    </div>
  );
}
