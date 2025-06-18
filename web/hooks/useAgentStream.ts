import { useState, useEffect, useRef, useCallback } from 'react';

// Clean event types following 2025 best practices
export interface StreamEvent {
  event: 'thinking' | 'sql' | 'data' | 'answer' | 'done' | 'error';
  data: string;
  id?: string;
}

export interface AgentStreamState {
  thinking: string;
  sql: string | null;
  data: any | null;
  answer: string | null;
  isStreaming: boolean;
  error: string | null;
}

interface UseAgentStreamResult extends AgentStreamState {
  startStream: (query: string) => void;
  stopStream: () => void;
  reset: () => void;
}

export function useAgentStream(): UseAgentStreamResult {
  // Simple, flat state - no complex objects
  const [thinking, setThinking] = useState<string>('');
  const [sql, setSql] = useState<string | null>(null);
  const [data, setData] = useState<any | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const queryIdRef = useRef<string | null>(null);

  // Clean reset function
  const reset = useCallback(() => {
    setThinking('');
    setSql(null);
    setData(null);
    setAnswer(null);
    setIsStreaming(false);
    setError(null);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    queryIdRef.current = null;
  }, []);

  // Stop stream
  const stopStream = useCallback(() => {
    setIsStreaming(false);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Start stream following 2025 pattern
  const startStream = useCallback(async (query: string) => {
    reset();
    setIsStreaming(true);

    try {
      // Connect directly to streaming endpoint
      const eventSource = new EventSource(
        `/api/nl2sql/agent/v2/stream?` +
        new URLSearchParams({
          question: query,
          max_iterations: '10'
        })
      );
      eventSourceRef.current = eventSource;

      // Handle events following the clean protocol
      eventSource.addEventListener('thinking', (event) => {
        setThinking(prev => prev + event.data);
      });

      eventSource.addEventListener('sql', (event) => {
        setSql(event.data);
      });

      eventSource.addEventListener('data', (event) => {
        try {
          setData(JSON.parse(event.data));
        } catch (e) {
          console.warn('Failed to parse data event:', e);
        }
      });

      eventSource.addEventListener('answer', (event) => {
        setAnswer(event.data);
      });

      eventSource.addEventListener('done', () => {
        setIsStreaming(false);
        eventSource.close();
      });

      eventSource.addEventListener('error', (event: MessageEvent) => {
        setError(event.data || 'Stream error occurred');
        setIsStreaming(false);
        eventSource.close();
      });

      // Handle connection errors
      eventSource.onerror = () => {
        setError('Connection to agent stream lost');
        setIsStreaming(false);
        eventSource.close();
      };

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start stream');
      setIsStreaming(false);
    }
  }, [reset]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    thinking,
    sql,
    data,
    answer,
    isStreaming,
    error,
    startStream,
    stopStream,
    reset,
  };
}
