'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';

interface Message {
  container_id: string;
  vm_name: string;
  icon_name: string;
  color: string;
  timestamp: string;
}

interface UpdateData {
  messages: Message[];
  last_poll: string;
  queue_size: number;
}

function DashboardContent() {
  const [isConnected, setIsConnected] = useState(false);
  const [vmStates, setVmStates] = useState<Map<string, Message>>(new Map());
  const [messageCount, setMessageCount] = useState(0);
  const [queueSize, setQueueSize] = useState(0);
  const [lastPoll, setLastPoll] = useState('-');
  const [showConfirm, setShowConfirm] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const searchParams = useSearchParams();
  
  useEffect(() => {
    // Get host from query params or use current hostname
    const host = searchParams.get('host') || window.location.hostname;
    const port = searchParams.get('port') || '8080';
    const wsUrl = `ws://${host}:${port}/ws`;
    
    connectWebSocket(wsUrl);
    
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [searchParams]);
  
  const connectWebSocket = (url: string) => {
    if (ws.current) {
      ws.current.close();
    }
    
    try {
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        setIsConnected(true);
        console.log('WebSocket connected');
      };
      
      ws.current.onclose = () => {
        setIsConnected(false);
        console.log('WebSocket disconnected, reconnecting in 5s...');
        setTimeout(() => connectWebSocket(url), 5000);
      };
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      ws.current.onmessage = (event) => {
        try {
          const data: UpdateData = JSON.parse(event.data);
          setLastPoll(data.last_poll);
          setMessageCount(prev => prev + data.messages.length);
          setQueueSize(data.queue_size);
          
          // Update VM states with new messages
          setVmStates(prevStates => {
            const updatedStates = new Map(prevStates);
            data.messages.forEach(msg => {
              updatedStates.set(msg.container_id, msg);
            });
            return updatedStates;
          });
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
    }
  };
  
  const clearQueue = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: 'clearQueue' }));
      setShowConfirm(false);
    }
  };
  
  return (
    <div className="flex flex-col min-h-screen bg-gray-50 text-gray-900">
      <div className="bg-white p-4 shadow-md flex justify-between items-center">
        <h1 className="text-xl md:text-2xl font-bold">Event Puller Dashboard</h1>
        <div className="flex items-center gap-4">
          <div className={`px-3 py-1 rounded text-sm ${isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
          <button 
            onClick={() => setShowConfirm(true)}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded transition-colors"
          >
            Clear Queue
          </button>
        </div>
      </div>
      
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg max-w-md w-full">
            <h2 className="text-lg font-bold mb-4">Confirm Queue Clear</h2>
            <p className="mb-6">Are you sure you want to clear the queue? This cannot be undone.</p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100"
              >
                Cancel
              </button>
              <button 
                onClick={clearQueue}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Clear Queue
              </button>
            </div>
          </div>
        </div>
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4">
        <div className="bg-white p-4 rounded shadow-md">
          <div className="text-sm text-gray-500 mb-1">Active VMs</div>
          <div className="text-2xl font-bold">{vmStates.size}</div>
        </div>
        <div className="bg-white p-4 rounded shadow-md">
          <div className="text-sm text-gray-500 mb-1">Queue Size</div>
          <div className="text-2xl font-bold">{queueSize}</div>
        </div>
        <div className="bg-white p-4 rounded shadow-md">
          <div className="text-sm text-gray-500 mb-1">Messages Processed</div>
          <div className="text-2xl font-bold">{messageCount}</div>
        </div>
        <div className="bg-white p-4 rounded shadow-md">
          <div className="text-sm text-gray-500 mb-1">Last Update</div>
          <div className="text-2xl font-bold">{lastPoll}</div>
        </div>
      </div>
      
      <div className="flex-1 p-4">
        <div className="bg-white p-4 rounded shadow-md">
          <h2 className="text-lg font-bold mb-4">Event Visualization</h2>
          <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-8 lg:grid-cols-12 gap-3">
            {Array.from(vmStates.entries()).map(([id, vm]) => (
              <div 
                key={id}
                className="flex flex-col items-center justify-center p-2 border-2 rounded-lg h-24 transition-transform hover:-translate-y-1"
                style={{ borderColor: vm.color }}
              >
                <div className="text-2xl mb-2" style={{ color: vm.color }}>{vm.icon_name}</div>
                <div className="text-xs font-medium text-center truncate w-full" title={`${vm.vm_name} (${id})`}>
                  {vm.vm_name}
                </div>
                <div className="text-xs text-gray-500 truncate w-full" title={id}>
                  {id.substring(0, 8)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="flex flex-col md:flex-row justify-between p-4 bg-white shadow-md mt-auto text-sm text-gray-600">
        <div>
          <span className="font-medium">CosmosDB Status:</span> {isConnected ? 'Connected' : 'Not Connected'}
        </div>
        <div suppressHydrationWarning>
          Event Puller Dashboard | {new Date().getFullYear()}
        </div>
      </div>
    </div>
  );
}

// Use Next.js dynamic import with SSR disabled to avoid hydration issues
const Dashboard = dynamic(() => Promise.resolve(DashboardContent), {
  ssr: false,
});

export default Dashboard;