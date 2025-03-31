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
      console.log('Attempting to connect to WebSocket:', url);
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        setIsConnected(true);
        console.log('WebSocket connected successfully');
      };

      ws.current.onclose = (event) => {
        setIsConnected(false);
        console.log('WebSocket disconnected:', event.code, event.reason);
        console.log('Reconnecting in 5s...');
        setTimeout(() => connectWebSocket(url), 5000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      // Add message queue to handle high-frequency updates
      let messageQueue: UpdateData[] = [];
      let isProcessing = false;
      let processingTimeout: NodeJS.Timeout | null = null;

      const processMessageQueue = () => {
        if (messageQueue.length === 0 || isProcessing) {
          return;
        }

        isProcessing = true;
        const batch = messageQueue;
        messageQueue = [];

        try {
          setLastPoll(batch[batch.length - 1].last_poll);
          setMessageCount(
            (prev) => prev + batch.reduce((acc, data) => acc + data.messages.length, 0),
          );
          setQueueSize(batch[batch.length - 1].queue_size);

          // Update VM states with new messages
          setVmStates((prevStates) => {
            const updatedStates = new Map(prevStates);
            batch.forEach((data) => {
              data.messages.forEach((msg) => {
                // Use a fallback identifier if hostname is empty
                const identifier =
                  msg.hostname || `${msg.region}-${msg.icon_name}-${msg.timestamp}`;
                updatedStates.set(identifier, { ...msg, hostname: identifier });
              });
            });
            return updatedStates;
          });
        } catch (error) {
          console.error('Error processing message batch:', error);
        } finally {
          isProcessing = false;
        }
      };

      // Override the onmessage handler to use the queue
      ws.current.onmessage = (event) => {
        try {
          console.log('Raw WebSocket message received:', event.data);
          const data: UpdateData = JSON.parse(event.data);
          console.log('Parsed WebSocket message:', data);
          messageQueue.push(data);

          // Clear any existing timeout
          if (processingTimeout) {
            clearTimeout(processingTimeout);
          }

          // Set a new timeout to process the queue
          processingTimeout = setTimeout(processMessageQueue, 100);
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
      // Attempt to reconnect after error
      setTimeout(() => connectWebSocket(url), 5000);
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
