'use client';

import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';

import NodeGraph from './NodeGraph';

export interface Message {
  job_id: string;
  execution_id: string;
  hostname: string;
  job_submission_time: string;
  icon_name: string;
  timestamp: string;
  color: string;
  sequence: number;
  region: string;
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
              updatedStates.set(msg.hostname, msg);
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
    <NodeGraph
      isConnected={isConnected}
      setOpenClearQueue={setShowConfirm}
      clearQueue={clearQueue}
      vmStates={vmStates}
      queueSize={queueSize}
      messageCount={messageCount}
      lastPoll={lastPoll}
      showConfirm={showConfirm}
    />
  );
}

// Use Next.js dynamic import with SSR disabled to avoid hydration issues
const Page = dynamic(() => Promise.resolve(DashboardContent), {
  ssr: false,
});

export default Page;
