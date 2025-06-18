import { useState, useCallback, useEffect, useRef } from 'react';
import { useDataSource } from '@/contexts/DataSourceContext';

interface AgentStep {
  id: string;
  type: 'thought' | 'action' | 'observation' | 'answer';
  content: string;
  iteration: number;
  timestamp: number;
}

interface AgentResult {
  sql?: string;
  results?: {
    columns: string[];
    data: any[];
    row_count: number;
  };
  answer?: string;
  summary?: string;
  metadata?: any;
}

interface UseAgentQueryV2Result {
  execute: (query: string) => void;
  reset: () => void;
  isStreaming: boolean;
  isComplete: boolean;
  steps: AgentStep[];
  result: AgentResult | null;
  error: string | null;
  queryId: string | null;
}

export function useAgentQueryV2(): UseAgentQueryV2Result {
  // State
  const [isStreaming, setIsStreaming] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queryId, setQueryId] = useState<string | null>(null);

  // Refs
  const eventSourceRef = useRef<EventSource | null>(null);
  const stepCounterRef = useRef(0);
  const hasCompletedRef = useRef(false);

  // Context
  const { sessionId } = useDataSource();

  // Reset function
  const reset = useCallback(() => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Reset state
    setIsStreaming(false);
    setIsComplete(false);
    setSteps([]);
    setResult(null);
    setError(null);
    setQueryId(null);
    stepCounterRef.current = 0;
    hasCompletedRef.current = false;
  }, []);

  // Execute query
  const execute = useCallback(async (query: string) => {
    // Reset state
    reset();

    try {
      // Start query
      setIsStreaming(true);

      const response = await fetch('/api/nl2sql/agent/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(sessionId && { 'X-Session-Id': sessionId }),
        },
        body: JSON.stringify({
          question: query,
          max_iterations: 10
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start agent query');
      }

      const data = await response.json();
      setQueryId(data.query_id);

      // Connect to SSE stream
      const eventSource = new EventSource(`/api/nl2sql/agent/stream/${data.query_id}`);
      eventSourceRef.current = eventSource;

      // Helper to create unique step ID
      const createStepId = (type: string, iteration: number) => {
        const id = `${type}-${iteration}-${stepCounterRef.current}-${Date.now()}`;
        stepCounterRef.current++;
        return id;
      };

      // Event handlers
      eventSource.addEventListener('thought', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[V2] Thought event:', data);
          setSteps(prev => {
            console.log('[V2] Current steps:', prev.length, 'Adding thought');
            return [...prev, {
              id: createStepId('thought', data.iteration),
              type: 'thought',
              content: data.content,
              iteration: data.iteration,
              timestamp: new Date(data.timestamp).getTime(),
            }];
          });
        } catch (e) {
          console.error('Failed to parse thought event:', e);
        }
      });

      eventSource.addEventListener('action', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setSteps(prev => [...prev, {
            id: createStepId('action', data.iteration),
            type: 'action',
            content: data.content,
            iteration: data.iteration,
            timestamp: new Date(data.timestamp).getTime(),
          }]);
        } catch (e) {
          console.error('Failed to parse action event:', e);
        }
      });

      eventSource.addEventListener('observation', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setSteps(prev => [...prev, {
            id: createStepId('observation', data.iteration),
            type: 'observation',
            content: data.content,
            iteration: data.iteration,
            timestamp: new Date(data.timestamp).getTime(),
          }]);
        } catch (e) {
          console.error('Failed to parse observation event:', e);
        }
      });

      eventSource.addEventListener('answer', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setSteps(prev => [...prev, {
            id: createStepId('answer', data.iteration),
            type: 'answer',
            content: data.content,
            iteration: data.iteration,
            timestamp: new Date(data.timestamp).getTime(),
          }]);
        } catch (e) {
          console.error('Failed to parse answer event:', e);
        }
      });

      eventSource.addEventListener('complete', async () => {
        console.log('[V2] Complete event received');
        hasCompletedRef.current = true;
        try {
          // Fetch final results
          const resultResponse = await fetch(`/api/nl2sql/agent/result/${data.query_id}`);
          if (resultResponse.ok) {
            const resultData = await resultResponse.json();
            console.log('[V2] Final result:', resultData);

            // Always set the result, even if it contains an error
            setResult(resultData.result || null);

            // Set error if present, but keep the result
            if (resultData.result?.error) {
              setError(resultData.result.error.message || 'Query processing failed');
            }
          }
        } catch (e) {
          console.error('Failed to fetch results:', e);
        } finally {
          setIsStreaming(false);
          setIsComplete(true);
          eventSource.close();
        }
      });

      eventSource.addEventListener('error', (event: MessageEvent) => {
        let errorMessage = 'Query failed';
        try {
          const data = JSON.parse(event.data);
          errorMessage = data.content || data.error || errorMessage;
        } catch {
          // Use default error message
        }
        hasCompletedRef.current = true;
        setError(errorMessage);
        setIsStreaming(false);
        setIsComplete(true);
        eventSource.close();
      });

      eventSource.onerror = () => {
        // Only treat as error if we haven't completed successfully
        if (eventSource.readyState === EventSource.CLOSED && !hasCompletedRef.current) {
          console.error('[V2] EventSource connection lost while streaming');
          setError('Connection to server lost');
          setIsStreaming(false);
          setIsComplete(true);
        }
      };

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute query');
      setIsStreaming(false);
      setIsComplete(true);
    }
  }, [reset, sessionId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    execute,
    reset,
    isStreaming,
    isComplete,
    steps,
    result,
    error,
    queryId,
  };
}
