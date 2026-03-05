"use client";

import { useEffect, useState, useRef } from "react";
import { useSocket } from "@/lib/socket";

export default function LogsPage() {
  const { logs: contextLogs } = useSocket();
  const [logs, setLogs] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Sync with context logs
    setLogs(contextLogs);
  }, [contextLogs]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">System Logs</h1>
      </div>

      <div className="flex-1 rounded-xl border bg-black/90 p-4 font-mono text-xs overflow-y-auto">
        <div className="space-y-1">
          {logs.length === 0 && (
            <div className="text-muted-foreground italic">Waiting for logs...</div>
          )}
          {logs.map((log, i) => (
            <div key={i} className="text-green-400 break-all">
              {log}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>
    </div>
  );
}
