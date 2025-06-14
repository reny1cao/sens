import { useState, useCallback, useEffect, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useDataSource } from '@/contexts/DataSourceContext';

export interface AgentEvent {
  type: 'thought' | 'action' | 'observation' | 'complete' | 'error' | 'connection';
  timestamp: string;
  iteration: number;
  content: string;
  metadata?: Record<string, any>;
}

export interface AgentStep {
  id: string;
  type: AgentEvent['type'];
  iteration: number;
  content: string;
  timestamp: number;
  metadata?: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'error';
}

interface UseAgentQueryResult {
  executeQuery: (question: string) => void;
  isLoading: boolean;
  steps: AgentStep[];
  result: any;
  error: Error | null;
  reset: () => void;
}

export function useAgentQuery(): UseAgentQueryResult {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const queryIdRef = useRef<string | null>(null);
  const { sessionId } = useDataSource();

  // Cleanup function
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    queryIdRef.current = null;
  }, []);

  // Reset state
  const reset = useCallback(() => {
    cleanup();
    setSteps([]);
    setResult(null);
    setError(null);
    setIsLoading(false);
  }, [cleanup]);

  // Start query mutation
  const startQueryMutation = useMutation({
    mutationFn: async (question: string) => {
      const response = await fetch('/api/nl2sql/agent/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(sessionId && { 'X-Session-Id': sessionId }),
        },
        body: JSON.stringify({ question, max_iterations: 10 }),
      });

      if (!response.ok) {
        throw new Error('Failed to start agent query');
      }

      return response.json();
    },
    onSuccess: (data) => {
      queryIdRef.current = data.query_id;
      connectToEventStream(data.query_id);
    },
    onError: (err) => {
      setError(err as Error);
      setIsLoading(false);
    },
  });

  // Connect to SSE stream
  const connectToEventStream = useCallback((queryId: string) => {
    cleanup(); // Close any existing connection

    const eventSource = new EventSource(`/api/nl2sql/agent/stream/${queryId}`);
    eventSourceRef.current = eventSource;

    // Handle different event types
    eventSource.addEventListener('connection', (event) => {
      console.log('Connected to agent stream');
    });

    eventSource.addEventListener('thought', (event) => {
      const data: AgentEvent = JSON.parse(event.data);
      addStep({
        id: `thought-${data.iteration}-${Date.now()}`,
        type: 'thought',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: 'completed',
      });
    });

    eventSource.addEventListener('action', (event) => {
      const data: AgentEvent = JSON.parse(event.data);
      addStep({
        id: `action-${data.iteration}-${Date.now()}`,
        type: 'action',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: 'running',
      });
    });

    eventSource.addEventListener('observation', (event) => {
      const data: AgentEvent = JSON.parse(event.data);

      // Mark previous action as completed
      setSteps(prev => prev.map(step =>
        step.type === 'action' && step.iteration === data.iteration && step.status === 'running'
          ? { ...step, status: 'completed' }
          : step
      ));

      addStep({
        id: `observation-${data.iteration}-${Date.now()}`,
        type: 'observation',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: data.metadata?.success ? 'completed' : 'error',
      });
    });

    eventSource.addEventListener('complete', async (event) => {
      const data: AgentEvent = JSON.parse(event.data);

      // Fetch final results
      if (queryIdRef.current) {
        try {
          const response = await fetch(`/api/nl2sql/agent/result/${queryIdRef.current}`);
          if (response.ok) {
            const resultData = await response.json();
            setResult(resultData.result);
          }
        } catch (err) {
          console.error('Failed to fetch results:', err);
        }
      }

      setIsLoading(false);
      cleanup();
    });

    eventSource.addEventListener('error', (event) => {
      const data: AgentEvent = JSON.parse(event.data);
      setError(new Error(data.content));
      setIsLoading(false);
      cleanup();
    });

    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      setError(new Error('Connection to agent stream lost'));
      setIsLoading(false);
      cleanup();
    };
  }, [cleanup]);

  // Add a step to the list
  const addStep = useCallback((step: AgentStep) => {
    setSteps(prev => [...prev, step]);
  }, []);

  // Execute query
  const executeQuery = useCallback((question: string) => {
    reset();
    setIsLoading(true);
    startQueryMutation.mutate(question);
  }, [reset, startQueryMutation]);

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  return {
    executeQuery,
    isLoading,
    steps,
    result,
    error,
    reset,
  };
}
