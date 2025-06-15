import { useState, useCallback, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useDataSource } from '@/contexts/DataSourceContext';
import type { QueryRequest, QueryResponse, ProcessingStep } from '@/types';

const INITIAL_STEPS: ProcessingStep[] = [
  { id: 'intent_extraction', name: 'Understanding your request', status: 'pending' },
  { id: 'schema_retrieval', name: 'Finding relevant data', status: 'pending' },
  { id: 'sql_generation', name: 'Generating SQL query', status: 'pending' },
  { id: 'sql_validation', name: 'Validating query', status: 'pending' },
  { id: 'sql_execution', name: 'Executing query', status: 'pending' },
];

function mapPipelineStepsToUI(pipelineMetrics: any): ProcessingStep[] {
  if (!pipelineMetrics?.steps) return INITIAL_STEPS;

  const stepMapping: Record<string, string> = {
    'intent_extraction': 'Understanding your request',
    'schema_retrieval': 'Finding relevant data',
    'sql_generation': 'Generating SQL query',
    'sql_validation': 'Validating query',
    'sql_execution': 'Executing query',
  };

  return pipelineMetrics.steps.map((step: any) => {
    const stepName = stepMapping[step.name] || step.name;
    const status = step.status === 'success' ? 'completed' :
                   step.status === 'failed' ? 'error' :
                   step.status === 'started' ? 'running' : 'pending';

    return {
      id: step.name,
      name: stepName,
      status,
      startTime: step.start_time ? new Date(step.start_time).getTime() : undefined,
      endTime: step.end_time ? new Date(step.end_time).getTime() : undefined,
      message: step.error || step.metadata?.message,
      details: step.metadata?.details ||
               (step.metadata?.schema_context ? `Found ${step.metadata.schema_context.tables?.length || 0} relevant tables` : undefined)
    };
  });
}

export function useQuery() {
  const [steps, setSteps] = useState<ProcessingStep[]>(INITIAL_STEPS);
  const [isPolling, setIsPolling] = useState(false);
  const { sessionId, activeSource } = useDataSource();

  const resetSteps = useCallback(() => {
    setSteps(INITIAL_STEPS.map(step => ({ ...step, status: 'pending' })));
  }, []);

  const mutation = useMutation({
    mutationFn: async (request: QueryRequest) => {
      resetSteps();
      setIsPolling(true);

      try {
        // Show initial running state
        setSteps(prev => prev.map((step, idx) =>
          idx === 0 ? { ...step, status: 'running', startTime: Date.now() } : step
        ));

        // Make the API call with session ID (only if not using default database)
        const response = await fetch('/api/nl2sql', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(sessionId && activeSource?.id !== 'default' && { 'X-Session-Id': sessionId }),
          },
          body: JSON.stringify(request),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Failed to process query');
        }

        const data: QueryResponse = await response.json();

        // Debug log the response data
        console.log('[useQuery] API response:', {
          hasData: !!data,
          dataKeys: data ? Object.keys(data) : null,
          hasResults: !!data?.results,
          resultsKeys: data?.results ? Object.keys(data.results) : null,
          rowCount: data?.results?.row_count,
          hasColumns: !!data?.results?.columns,
          hasRows: !!data?.results?.data,
          sql: data?.sql?.substring(0, 100),
          summary: data?.summary,
        });

        // Update steps based on pipeline metrics
        if (data.metadata?.pipeline_metrics) {
          const realSteps = mapPipelineStepsToUI(data.metadata.pipeline_metrics);
          setSteps(realSteps);
        } else {
          // Fallback: mark all as completed if no metrics
          setSteps(prev => prev.map(step => ({
            ...step,
            status: 'completed',
            endTime: Date.now()
          })));
        }

        setIsPolling(false);
        return data;
      } catch (error) {
        setIsPolling(false);

        // Mark the appropriate step as failed based on error
        const errorMessage = error instanceof Error ? error.message : 'An error occurred';
        let failedStepId = 'sql_execution'; // default

        if (errorMessage.includes('intent') || errorMessage.includes('understand')) {
          failedStepId = 'intent_extraction';
        } else if (errorMessage.includes('schema') || errorMessage.includes('table')) {
          failedStepId = 'schema_retrieval';
        } else if (errorMessage.includes('SQL') || errorMessage.includes('generate')) {
          failedStepId = 'sql_generation';
        } else if (errorMessage.includes('valid')) {
          failedStepId = 'sql_validation';
        }

        setSteps(prev => prev.map(step => {
          if (step.id === failedStepId) {
            return { ...step, status: 'error', message: errorMessage, endTime: Date.now() };
          }
          if (step.status === 'running') {
            return { ...step, status: 'completed', endTime: Date.now() };
          }
          return step;
        }));

        throw error;
      }
    },
  });

  const executeQuery = useCallback((question: string) => {
    mutation.mutate({ question });
  }, [mutation]);

  return {
    executeQuery,
    isLoading: mutation.isPending || isPolling,
    data: mutation.data,
    error: mutation.error,
    steps,
    resetSteps,
  };
}
