'use client';

import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';

import Stats from './components/Stats';
import Footer from './components/Footer';
import Visualization from './components/Visualization';

export interface Message {
  container_id: string;
  vm_name: string;
  icon_name: string;
  color: string;
  timestamp: string;
  region: string;
}

interface UpdateData {
  messages: Message[];
  last_poll: string;
  queue_size: number;
}

function DashboardContent() {
  const [isConnected, setIsConnected] = useState(false);
  const [vmStates, setVmStates] = useState<Map<string, Message>>(
    new Map([
      [
        'placeholder1',
        {
          container_id: 'container1',
          vm_name: 'vmname1',
          icon_name: '🚀',
          color: '#00ff00',
          timestamp: 'test',
          region: 'us-east-1',
        },
      ],
      [
        'placeholder2',
        {
          container_id: 'container2',
          vm_name: 'vmname2',
          icon_name: '🔥',
          color: '#0000ff',
          timestamp: 'test',
          region: 'us-east-2',
        },
      ],
    ]),
  );

  const [messageCount, setMessageCount] = useState(0);
  const [queueSize, setQueueSize] = useState(0);
  const [lastPoll, setLastPoll] = useState('-');
  const [showConfirm, setShowConfirm] = useState(false);

  const ws = useRef<WebSocket | null>(null);
  const searchParams = useSearchParams();

  useEffect(() => {
    // Get WebSocket URL: Prioritize env var, then query params, then defaults
    const envWsUrl = process.env.NEXT_PUBLIC_WS_URL;
    const hostQuery = searchParams.get('host');
    const portQuery = searchParams.get('port');

    let wsUrl: string;

    if (envWsUrl) {
      wsUrl = envWsUrl;
      console.log(`Using WebSocket URL from environment: ${wsUrl}`);
    } else if (hostQuery) {
      const port = portQuery || '8080';
      wsUrl = `ws://${hostQuery}:${port}/ws`;
      console.log(`Using WebSocket URL from query params: ${wsUrl}`);
    } else {
      // Default for cases where env var and query params are not set
      // This might happen in production deployments or if .env.local is missing
      const defaultHost = window.location.hostname;
      const defaultPort = '8080'; // Assuming backend runs on 8080 by default
      wsUrl = `ws://${defaultHost}:${defaultPort}/ws`;
      console.log(`Using default WebSocket URL based on hostname: ${wsUrl}`);
    }

    connectWebSocket(wsUrl);
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        console.log('Received message:', event.data);

        try {
          const data: UpdateData = JSON.parse(event.data);
          setLastPoll(data.last_poll);
          setMessageCount((prev) => prev + data.messages.length);
          setQueueSize(data.queue_size);

          // Update VM states with new messages - using vm_name as the unique key
          setVmStates((prevStates) => {
            const updatedStates = new Map(prevStates);
            data.messages.forEach((msg) => {
              // Use vm_name as the key instead of container_id
              updatedStates.set(msg.vm_name, msg);
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
    <div className="flex min-h-screen flex-col bg-gray-100 text-gray-900">
      <div className="flex items-center justify-between bg-white p-4 shadow-md">
        <h1 className="text-xl font-bold md:text-2xl">Event Puller Dashboard</h1>
        <div className="flex items-center gap-4">
          <div
            className={`px-3 py-1 text-sm ${isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
          <button
            onClick={() => setShowConfirm(true)}
            className="cursor-pointer bg-red-600 px-2 py-1 text-sm text-white transition-colors hover:bg-red-700"
          >
            Clear Queue
          </button>
        </div>
      </div>

      {showConfirm && <ClearQueueModal setShowConfirm={setShowConfirm} clearQueue={clearQueue} />}

      <Stats
        vmStates={vmStates}
        queueSize={queueSize}
        messageCount={messageCount}
        lastPoll={lastPoll}
      />

      <Visualization vmStates={vmStates} />

      <Footer isConnected={isConnected} />
    </div>
  );
}

interface ClearQueueModalProps {
  setShowConfirm: (show: boolean) => void;
  clearQueue: () => void;
}

function ClearQueueModal({ setShowConfirm, clearQueue }: ClearQueueModalProps) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-bold">Confirm Queue Clear</h2>
        <p className="mb-6">Are you sure you want to clear the queue? This cannot be undone.</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setShowConfirm(false)}
            className="cursor-pointer rounded border border-gray-300 px-4 py-2 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            onClick={clearQueue}
            className="cursor-pointer rounded bg-red-600 px-4 py-2 text-white hover:bg-red-700"
          >
            Clear Queue
          </button>
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