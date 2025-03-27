import { truncateText } from '@/lib/utils';
import { Message } from '@/page';
import { useEffect, useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';

interface VMCardProps {
  message: Message;
}

function getContrastTextColor(hexColor: string): string {
  // Remove the hash if it's there
  const color = hexColor.charAt(0) === '#' ? hexColor.substring(1) : hexColor;
  const r = parseInt(color.substring(0, 2), 16);
  const g = parseInt(color.substring(2, 4), 16);
  const b = parseInt(color.substring(4, 6), 16);

  // Calculate brightness
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? 'black' : 'white';
}

export default function VMCard({ message }: Readonly<VMCardProps>) {
  const [showIcon, setShowIcon] = useState(false);

  useEffect(() => {
    setShowIcon(true);
    const timeout = setTimeout(() => {
      setShowIcon(false);
    }, 500);
    return () => clearTimeout(timeout);
  }, [message]);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <div
          key={message.vm_name}
          className="relative flex h-24 cursor-pointer flex-col items-center justify-center rounded-sm p-2 hover:-translate-y-1"
          style={{ backgroundColor: message.color, color: getContrastTextColor(message.color) }}
        >
          {/* Icon (flash when updated) */}
          <div
            className={`pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity duration-500 ${showIcon ? 'opacity-100' : 'opacity-0'}`}
          >
            <div className="text-2xl">{message.icon_name}</div>
          </div>

          {/* Content */}
          <div
            className={`transition-opacity duration-500 ${showIcon ? 'opacity-0' : 'opacity-100'}`}
          >
            <div
              className="w-full truncate text-center text-xs font-medium"
              title={message.vm_name}
            >
              {truncateText(message.vm_name, 8)}
            </div>
            <div className="w-full truncate text-xs" title={message.container_id}>
              {truncateText(message.container_id, 8)}
            </div>
          </div>
        </div>
      </PopoverTrigger>
      <PopoverContent>
        <div className="text-sm">
          <p>{message.vm_name}</p>
          <p>{message.container_id}</p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
