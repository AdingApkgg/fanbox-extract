"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

interface AppState {
  running: boolean;
  progress: number;
  status: string;
}

interface SocketContextType {
  state: AppState;
  logs: string[];
  connected: boolean;
}

const SocketContext = createContext<SocketContextType>({
  state: { running: false, progress: 0, status: "" },
  logs: [],
  connected: false,
});

export function SocketProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>({ running: false, progress: 0, status: "" });
  const [logs, setLogs] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // In dev mode, Next.js proxy handles /api, but WS might need direct connection or special config
    // Trying standard relative path first which works if proxy is correct
    // If running separately, might need localhost:8000
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // NOTE: In local dev with `next dev`, the rewrite proxy supports WS usually.
    const wsUrl = `${protocol}//${host}/api/ws`; 
    
    let ws: WebSocket | null = null;
    let retryTimeout: NodeJS.Timeout;

    const connect = () => {
      // Direct connection to Bun server port 3001 for WebSocket
      // Because Next.js rewrite proxy for WS is sometimes flaky or needs config
      ws = new WebSocket("ws://localhost:3001");

      ws.onopen = () => {
        console.log("WS Connected");
        setConnected(true);
      };

      ws.onclose = () => {
        console.log("WS Disconnected");
        setConnected(false);
        // Retry connection
        retryTimeout = setTimeout(connect, 3000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "state") {
            setState({
              running: data.running,
              progress: data.progress,
              status: data.status,
            });
          } else if (data.type === "log") {
            setLogs((prev) => {
              const newLogs = [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`];
              return newLogs.slice(-1000); // Keep last 1000
            });
            // Update running state based on logs
            setState(prev => ({
                ...prev,
                running: true,
                status: data.message.length > 60 ? data.message.substring(0, 60) + '...' : data.message
            }));
          } else if (data.type === "status") {
              // Handle simple status updates
              setState(prev => ({
                  ...prev,
                  status: data.message || data.status,
                  running: data.status !== 'stopped' && data.status !== 'error'
              }));
          }
        } catch (e) {
          console.error("WS Parse Error", e);
        }
      };
    };

    connect();

    return () => {
      if (ws) ws.close();
      clearTimeout(retryTimeout);
    };
  }, []);

  return (
    <SocketContext.Provider value={{ state, logs, connected }}>
      {children}
    </SocketContext.Provider>
  );
}

export const useSocket = () => useContext(SocketContext);
