import { useState, useCallback, useRef } from 'react';
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
  error?: {
    code: string;
    message: string;
  };
}

interface AgentEvent {
  type: string;
  timestamp: string;
  iteration: number;
  content: string;
  metadata?: any;
}

export interface UseAgentQueryV4Result {
  execute: (query: string) => Promise<void>;
  reset: () => void;

  // States
  queryId: string | null;
  isLoading: boolean;

  // Results
  steps: AgentStep[];
  result: AgentResult | null;
  error: string | null;

  // Detailed status
  status: 'idle' | 'connecting' | 'streaming' | 'fetching' | 'complete' | 'error';
}

export function useAgentQueryV4(): UseAgentQueryV4Result {
  // Core state
  const [queryId, setQueryId] = useState<string | null>(null);
  const [status, setStatusState] = useState<'idle' | 'connecting' | 'streaming' | 'fetching' | 'complete' | 'error'>('idle');
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs
  const eventSourceRef = useRef<EventSource | null>(null);
  const stepCounterRef = useRef(0);
  const statusRef = useRef<'idle' | 'connecting' | 'streaming' | 'fetching' | 'complete' | 'error'>('idle');

  // Context
  const { sessionId } = useDataSource();

  // Custom setStatus that updates both state and ref
  const setStatus = useCallback((newStatus: 'idle' | 'connecting' | 'streaming' | 'fetching' | 'complete' | 'error') => {
    setStatusState(newStatus);
    statusRef.current = newStatus;
  }, []);

  // Computed values
  const isLoading = status === 'connecting' || status === 'streaming' || status === 'fetching';

  // Reset function
  const reset = useCallback(() => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Reset all state
    setQueryId(null);
    setStatus('idle');
    setSteps([]);
    setResult(null);
    setError(null);
    stepCounterRef.current = 0;
  }, []);

  // Execute query
  const execute = useCallback(async (query: string) => {
    console.log('[V4] Executing query:', query);

    // Reset state
    reset();
    setStatus('connecting');

    try {
      // Start query
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
        throw new Error(`Failed to start query: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[V4] Query started:', data);

      setQueryId(data.query_id);
      setStatus('streaming');

      // Connect to SSE stream
      const eventSource = new EventSource(`/api/nl2sql/agent/stream/${data.query_id}`);
      eventSourceRef.current = eventSource;

      // Helper to create unique step ID
      const createStepId = (type: string, iteration: number) => {
        const id = `${type}-${iteration}-${stepCounterRef.current}`;
        stepCounterRef.current++;
        return id;
      };

      // Process incoming events
      const processEvent = (event: AgentEvent, type: AgentStep['type']) => {
        const step: AgentStep = {
          id: createStepId(type, event.iteration),
          type,
          content: event.content,
          iteration: event.iteration,
          timestamp: new Date(event.timestamp).getTime(),
        };

        setSteps(prev => [...prev, step]);
        console.log('[V4] Added step:', type, event.iteration, event.content.substring(0, 50));
      };

      // Event handlers
      eventSource.addEventListener('thought', (e) => {
        try {
          const data = JSON.parse(e.data);
          processEvent(data, 'thought');
        } catch (err) {
          console.error('[V4] Failed to parse thought event:', err);
        }
      });

      eventSource.addEventListener('action', (e) => {
        try {
          const data = JSON.parse(e.data);
          processEvent(data, 'action');
        } catch (err) {
          console.error('[V4] Failed to parse action event:', err);
        }
      });

      eventSource.addEventListener('observation', (e) => {
        try {
          const data = JSON.parse(e.data);
          processEvent(data, 'observation');
        } catch (err) {
          console.error('[V4] Failed to parse observation event:', err);
        }
      });

      eventSource.addEventListener('answer', (e) => {
        try {
          const data = JSON.parse(e.data);
          processEvent(data, 'answer');
        } catch (err) {
          console.error('[V4] Failed to parse answer event:', err);
        }
      });

      // Handle completion
      eventSource.addEventListener('complete', async (e) => {
        console.log('[V4] Complete event received');
        setStatus('fetching');

        try {
          // Parse complete event data for immediate info
          const completeData = JSON.parse(e.data);
          console.log('[V4] Complete data:', completeData);

          // Fetch final results
          const resultResponse = await fetch(`/api/nl2sql/agent/result/${data.query_id}`);
          if (!resultResponse.ok) {
            throw new Error('Failed to fetch results');
          }

          const resultData = await resultResponse.json();
          console.log('[V4] Final result:', resultData);

          // Handle the result
          if (resultData.status === 'completed' && resultData.result) {
            setResult(resultData.result);

            // If there's an error in the result, set it but keep the result
            if (resultData.result.error) {
              setError(resultData.result.error.message);
              setStatus('error');
            } else {
              setStatus('complete');
            }
          } else if (resultData.status === 'error') {
            setError(resultData.error || 'Query processing failed');
            setStatus('error');
          } else {
            setError('Unexpected result format');
            setStatus('error');
          }
        } catch (err) {
          console.error('[V4] Failed to fetch results:', err);
          setError('Failed to fetch query results');
          setStatus('error');
        } finally {
          eventSource.close();
        }
      });

      // Handle SSE errors
      eventSource.addEventListener('error', (e: MessageEvent) => {
        console.log('[V4] SSE error event:', e);

        // Try to parse error data
        if (e.data) {
          try {
            const errorData = JSON.parse(e.data);
            setError(errorData.content || errorData.error || 'Query failed');
          } catch {
            setError('Query failed');
          }
        }

        setStatus('error');
        eventSource.close();
      });

      // Handle connection errors
      eventSource.onerror = (e) => {
        // Only treat as error if we're not already complete
        if (statusRef.current !== 'complete' && statusRef.current !== 'error' && statusRef.current !== 'fetching') {
          console.error('[V4] EventSource connection error, current status:', statusRef.current);
          setError('Lost connection to server');
          setStatus('error');
        } else {
          console.log('[V4] EventSource closed normally, status:', statusRef.current);
        }
      };

    } catch (err) {
      console.error('[V4] Query execution failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to execute query');
      setStatus('error');
    }
  }, [reset, sessionId, status]);

  return {
    execute,
    reset,
    queryId,
    isLoading,
    steps,
    result,
    error,
    status,
  };
}
