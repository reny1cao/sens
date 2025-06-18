"use client";

import { useEffect, useState } from "react";

interface DebugPanelProps {
  queryId: string | null;
  steps: any[];
  isStreaming: boolean;
  isComplete: boolean;
  error: string | null;
  result: any;
}

export function DebugPanel({ queryId, steps, isStreaming, isComplete, error, result }: DebugPanelProps) {
  const [events, setEvents] = useState<string[]>([]);

  useEffect(() => {
    const timestamp = new Date().toLocaleTimeString();
    const status = `[${timestamp}] Query: ${queryId || 'none'}, Streaming: ${isStreaming}, Complete: ${isComplete}, Steps: ${steps.length}, Error: ${error || 'none'}`;
    setEvents(prev => [...prev.slice(-50), status]);
  }, [queryId, steps.length, isStreaming, isComplete, error]);

  return (
    <div className="fixed bottom-0 right-0 w-96 h-64 bg-black text-green-400 p-2 font-mono text-xs overflow-y-auto">
      <div className="font-bold mb-2">DEBUG PANEL</div>
      <div className="space-y-1">
        {events.map((event, i) => (
          <div key={i} className="opacity-80">{event}</div>
        ))}
      </div>
      <div className="mt-2 border-t border-green-600 pt-2">
        <div>Current Steps ({steps.length}):</div>
        {steps.slice(-5).map((step, i) => (
          <div key={i} className="ml-2 text-xs opacity-60">
            [{step.type}] {step.content.substring(0, 50)}...
          </div>
        ))}
      </div>
    </div>
  );
}
