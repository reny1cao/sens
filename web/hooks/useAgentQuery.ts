import { useState, useCallback, useEffect, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useDataSource } from '@/contexts/DataSourceContext';

export interface AgentEvent {
  type: 'thought' | 'action' | 'observation' | 'answer' | 'complete' | 'error' | 'connection';
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
  error: string | null;
  reset: () => void;
}

export function useAgentQuery(): UseAgentQueryResult {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
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
      setError(err instanceof Error ? err.message : 'Failed to start query');
      setIsLoading(false);
    },
  });

  // Connect to SSE stream
  const connectToEventStream = useCallback((queryId: string) => {
    cleanup(); // Close any existing connection

    console.log('[useAgentQuery] Connecting to stream for query:', queryId);
    const eventSource = new EventSource(`/api/nl2sql/agent/stream/${queryId}`);
    eventSourceRef.current = eventSource;

    // Handle different event types
    eventSource.addEventListener('connection', (event) => {
      console.log('[useAgentQuery] Connected to agent stream');
    });

    eventSource.addEventListener('thought', (event: MessageEvent) => {
      const data: AgentEvent = JSON.parse(event.data);
      addStep({
        id: '', // Will be set by addStep
        type: 'thought',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: 'completed',
      });
    });

    eventSource.addEventListener('action', (event: MessageEvent) => {
      const data: AgentEvent = JSON.parse(event.data);
      addStep({
        id: '', // Will be set by addStep
        type: 'action',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: 'running',
      });
    });

    eventSource.addEventListener('observation', (event: MessageEvent) => {
      const data: AgentEvent = JSON.parse(event.data);

      // Mark previous action as completed
      setSteps(prev => prev.map(step =>
        step.type === 'action' && step.iteration === data.iteration && step.status === 'running'
          ? { ...step, status: 'completed' }
          : step
      ));

      addStep({
        id: '', // Will be set by addStep
        type: 'observation',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: data.metadata?.success ? 'completed' : 'error',
      });
    });

    eventSource.addEventListener('answer', (event: MessageEvent) => {
      const data: AgentEvent = JSON.parse(event.data);
      console.log('[useAgentQuery] Answer event received:', data);

      addStep({
        id: '', // Will be set by addStep
        type: 'answer',
        iteration: data.iteration,
        content: data.content,
        timestamp: new Date(data.timestamp).getTime(),
        metadata: data.metadata,
        status: 'completed',
      });
    });

    eventSource.addEventListener('complete', async (event: MessageEvent) => {
      const data: AgentEvent = JSON.parse(event.data);
      console.log('[useAgentQuery] Complete event received:', data);

      // Fetch final results
      if (queryIdRef.current) {
        try {
          console.log('[useAgentQuery] Fetching results for query:', queryIdRef.current);
          const response = await fetch(`/api/nl2sql/agent/result/${queryIdRef.current}`);
          console.log('[useAgentQuery] Result response status:', response.status);

          if (response.ok) {
            const resultData = await response.json();
            console.log('[useAgentQuery] Full result response:', resultData);
            console.log('[useAgentQuery] Result data structure:', {
              status: resultData.status,
              hasResult: !!resultData.result,
              resultKeys: resultData.result ? Object.keys(resultData.result) : null,
              resultsInResult: resultData.result?.results,
              dataInResults: resultData.result?.results?.data,
            });
            setResult(resultData.result);
          } else {
            const errorText = await response.text();
            console.error('[useAgentQuery] Result fetch failed:', errorText);
          }
        } catch (err) {
          console.error('[useAgentQuery] Failed to fetch results:', err);
        }
      }

      setIsLoading(false);
      cleanup();
    });

    eventSource.addEventListener('error', (event: MessageEvent) => {
      const data: AgentEvent = JSON.parse(event.data);
      setError(data.content);
      setIsLoading(false);
      cleanup();
    });

    // Generic message handler to catch any untyped events
    eventSource.onmessage = (event) => {
      console.log('[useAgentQuery] Generic message received:', event);
    };

    eventSource.onerror = (err) => {
      console.error('[useAgentQuery] EventSource error:', err);
      setError('Connection to agent stream lost');
      setIsLoading(false);
      cleanup();
    };
  }, [cleanup]);

  // Add a step to the list with unique ID generation
  const addStep = useCallback((step: AgentStep) => {
    setSteps(prev => {
      // Generate truly unique ID using counter
      const uniqueId = `${step.type}-${step.iteration}-${prev.length}-${Date.now()}`;
      return [...prev, { ...step, id: uniqueId }];
    });
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
