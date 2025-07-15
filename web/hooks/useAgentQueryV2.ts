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
  success?: boolean;
  error?: string;
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
          max_iterations: 25
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

      // Debug: Log all events
      eventSource.onmessage = (event) => {
        console.log('[V2] Raw SSE message - type:', event.type, 'data:', event.data);
      };

      // Add generic event listener to catch any missed events
      eventSource.addEventListener('message', (event: MessageEvent) => {
        console.log('[V2] Generic message event:', event.type, event.data);
      });

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
          console.log('[V2] Answer event:', data);
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

      eventSource.addEventListener('result', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[V2] Result event:', data);

          // The content contains the actual result
          const resultData = data.content;
          console.log('[V2] Processing result data:', resultData);

          if (resultData) {
            // Check if we have SQL execution results
            if (resultData.result && typeof resultData.result === 'object') {
              // Transform the result to match frontend expectations
              const sqlResult = resultData.result;

              // Convert rows array to data array with column names
              if (sqlResult.rows && sqlResult.columns) {
                sqlResult.data = sqlResult.rows.map((row: any[]) => {
                  const obj: any = {};
                  sqlResult.columns.forEach((col: string, idx: number) => {
                    obj[col] = row[idx];
                  });
                  return obj;
                });
                console.log('[V2] Converted rows to data:', sqlResult.data);
              }

              // Create the expected structure
              const finalResult = {
                results: sqlResult,
                sql: resultData.sql,
                answer: resultData.answer,
                success: resultData.success !== false // Default to true if not explicitly false
              };
              console.log('[V2] Setting final result:', finalResult);
              setResult(finalResult);

              // Check for errors in the result
              if (resultData.error) {
                setError(resultData.error);
              } else {
                // Clear any previous errors since we have a successful result
                setError(null);
              }
            } else if (resultData.answer || resultData.direct_answer) {
              // Direct conversational answer without SQL
              const finalResult = {
                answer: resultData.answer || resultData.direct_answer,
                success: resultData.success !== false
              };
              console.log('[V2] Setting conversational result:', finalResult);
              setResult(finalResult);
              // Clear any previous errors
              setError(null);
            } else if (resultData.error) {
              // Error case
              console.log('[V2] Error in result:', resultData.error);
              setError(resultData.error);
              setResult({
                success: false,
                error: resultData.error
              });
            } else {
              // Fallback - set the raw result
              console.log('[V2] Setting raw result data');
              setResult(resultData);
            }
          } else {
            console.log('[V2] No result data found');
            setResult(null);
          }
        } catch (e) {
          console.error('Failed to parse result event:', e);
        }
      });

      eventSource.addEventListener('complete', async () => {
        console.log('[V2] Complete event received');
        hasCompletedRef.current = true;

        // Implement polling with exponential backoff to ensure we get the result
        const maxAttempts = 5;
        const baseDelay = 50; // Start with 50ms

        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          try {
            const delay = baseDelay * Math.pow(2, attempt); // 50, 100, 200, 400, 800ms
            if (attempt > 0) {
              await new Promise(resolve => setTimeout(resolve, delay));
            }

            const resultResponse = await fetch(`/api/nl2sql/agent/result/${data.query_id}`);
            if (resultResponse.ok) {
              const resultData = await resultResponse.json();
              console.log('[V2] Fetched final result on attempt', attempt + 1, ':', resultData);

              if (resultData.result) {
                // Transform the result to match frontend expectations
                const result = resultData.result.result || resultData.result;

                // Convert rows array to data array with column names if needed
                if (result.rows && result.columns && !result.data) {
                  result.data = result.rows.map((row: any[]) => {
                    const obj: any = {};
                    result.columns.forEach((col: string, idx: number) => {
                      obj[col] = row[idx];
                    });
                    return obj;
                  });
                }

                // Set the final result - merge with what we already have
                setResult(prevResult => ({
                  ...prevResult,
                  results: result,
                  sql: resultData.result.sql || prevResult?.sql,
                  answer: resultData.result.answer || prevResult?.answer,
                  success: resultData.result.success !== false
                }));

                // Check for errors
                if (resultData.result.error) {
                  setError(resultData.result.error);
                } else {
                  // Clear any previous errors if the result is successful
                  setError(null);
                }
              }
              break; // Success, exit the retry loop
            } else if (attempt === maxAttempts - 1) {
              console.error('[V2] Failed to fetch result after', maxAttempts, 'attempts:', resultResponse.status);
            }
          } catch (e) {
            if (attempt === maxAttempts - 1) {
              console.error('[V2] Error fetching results after', maxAttempts, 'attempts:', e);
            }
          }
        }

        // Mark as complete and close the stream
        setIsStreaming(false);
        eventSource.close();

        // Only mark as complete after we've attempted to fetch the result
        // This prevents the brief "failed" state
        setIsComplete(true);

        // Clean up event handler from agent
        if (eventSourceRef.current) {
          eventSourceRef.current = null;
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
