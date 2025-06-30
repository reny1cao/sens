/**
 * React hook for BIRD-CRITIC evaluation with streaming support.
 * Provides real-time updates of evaluation progress and agent thinking steps.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

export interface EvaluationConfig {
  limit?: number;
  database_prefix?: string;
  debug_mode?: boolean;
  max_iterations?: number;
}

export interface EvaluationStatus {
  evaluation_id: string;
  status: 'running' | 'completed' | 'failed';
  total_tasks: number;
  completed_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  current_task?: string;
  start_time: string;
  end_time?: string;
  metrics: Record<string, any>;
}

export interface TaskResult {
  task_id: string;
  db_id: string;
  query: string;
  success: boolean;
  sql?: string;
  error?: string;
  execution_time_ms?: number;
  result_count?: number;
  prompt_flow?: Array<{
    model: string;
    prompt: string;
    response: string;
  }>;
}

export interface AgentEvent {
  type: string;
  data: any;
  timestamp?: string;
}

export interface EvaluationEvent {
  type: 'evaluation_start' | 'task_start' | 'agent_event' | 'task_complete' | 'metrics_update' | 'evaluation_complete' | 'evaluation_error' | 'task_error';
  evaluation_id?: string;
  task_id?: string;
  task_number?: number;
  total_tasks?: number;
  event?: AgentEvent;
  metrics?: Record<string, any>;
  success?: boolean;
  sql?: string;
  error?: string;
  output_files?: Record<string, string>;
  final_metrics?: Record<string, any>;
}

export interface UseBirdCriticEvaluationResult {
  // Status
  status: EvaluationStatus | null;
  isRunning: boolean;
  isCompleted: boolean;

  // Data
  currentTask: TaskResult | null;
  completedTasks: TaskResult[];
  agentEvents: AgentEvent[];
  currentMetrics: Record<string, any>;

  // Actions
  startEvaluation: (config: EvaluationConfig) => Promise<void>;
  stopEvaluation: () => void;
  clearHistory: () => void;

  // Export
  exportResults: (format: 'submission' | 'detailed' | 'sql_only' | 'metrics') => Promise<void>;

  // Error handling
  error: string | null;
  retry: () => void;
}

export function useBirdCriticEvaluation(): UseBirdCriticEvaluationResult {
  const [status, setStatus] = useState<EvaluationStatus | null>(null);
  const [currentTask, setCurrentTask] = useState<TaskResult | null>(null);
  const [completedTasks, setCompletedTasks] = useState<TaskResult[]>([]);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const [lastConfig, setLastConfig] = useState<EvaluationConfig | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const currentEvaluationId = useRef<string | null>(null);

  const stopEvaluation = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    currentEvaluationId.current = null;
  }, []);

  const startEvaluation = useCallback(async (config: EvaluationConfig) => {
    try {
      setError(null);
      setLastConfig(config);

      // Stop any existing evaluation
      stopEvaluation();

      // Clear previous data
      setCompletedTasks([]);
      setAgentEvents([]);
      setCurrentTask(null);
      setCurrentMetrics({});

      // Start new evaluation
      console.log('Sending evaluation config to backend:', config);
      const response = await fetch('/api/evaluation/bird-critic/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      });

      console.log('Backend response status:', response.status);

      if (!response.ok) {
        throw new Error(`Failed to start evaluation: ${response.statusText}`);
      }

      const initialStatus: EvaluationStatus = await response.json();
      setStatus(initialStatus);
      currentEvaluationId.current = initialStatus.evaluation_id;

      // Start streaming
      const eventSource = new EventSource(
        `/api/evaluation/bird-critic/stream/${initialStatus.evaluation_id}`
      );
      eventSourceRef.current = eventSource;

      // Handle generic onmessage for events without specific types
      eventSource.onmessage = (event) => {
        try {
          const data: EvaluationEvent = JSON.parse(event.data);

          switch (data.type) {
            case 'evaluation_start':
              // Status already set from initial response
              break;

            case 'task_start':
              setCurrentTask({
                task_id: data.task_id!,
                db_id: data.db_id || '',
                query: data.query || '',
                success: false,
              });
              setAgentEvents([]); // Clear events for new task
              // Update status with current task info
              setStatus(prev => prev ? {
                ...prev,
                current_task: data.task_id!,
                completed_tasks: (data.task_number || 1) - 1
              } : null);
              break;

            case 'task_complete':
              const taskResult: TaskResult = {
                task_id: data.task_id!,
                db_id: data.db_id || '',
                query: data.query || '',
                success: data.success!,
                sql: data.sql,
                error: data.error,
                execution_time_ms: data.execution_time_ms,
                result_count: data.result_count,
                prompt_flow: data.prompt_flow,
              };
              setCompletedTasks(prev => [...prev, taskResult]);
              setCurrentTask(null);
              // Update status counters
              setStatus(prev => prev ? {
                ...prev,
                completed_tasks: prev.completed_tasks + 1,
                successful_tasks: data.success ? prev.successful_tasks + 1 : prev.successful_tasks,
                failed_tasks: !data.success ? prev.failed_tasks + 1 : prev.failed_tasks,
                current_task: null
              } : null);
              break;

            case 'metrics_update':
              if (data.metrics) {
                setCurrentMetrics(data.metrics);
              }
              break;

            case 'evaluation_complete':
              setStatus(prev => prev ? {
                ...prev,
                status: 'completed',
                end_time: new Date().toISOString(),
              } : null);
              if (data.final_metrics) {
                setCurrentMetrics(data.final_metrics);
              }
              stopEvaluation();
              break;

            case 'evaluation_error':
              setError(data.error || 'Unknown evaluation error');
              setStatus(prev => prev ? {
                ...prev,
                status: 'failed',
                end_time: new Date().toISOString(),
              } : null);
              stopEvaluation();
              break;

            case 'task_error':
              console.warn('Task error:', data.error);
              // Update failed task counter
              setStatus(prev => prev ? {
                ...prev,
                failed_tasks: prev.failed_tasks + 1,
                completed_tasks: prev.completed_tasks + 1
              } : null);
              break;
          }
        } catch (err) {
          console.error('Failed to parse SSE message:', err);
        }
      };

      // Add specific event listeners for agent events (like chat system)
      eventSource.addEventListener('thought', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setAgentEvents(prev => [...prev, {
            type: 'thought',
            data: data,
            timestamp: data.timestamp,
          }]);
        } catch (e) {
          console.error('Failed to parse thought event:', e);
        }
      });

      eventSource.addEventListener('action', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setAgentEvents(prev => [...prev, {
            type: 'action',
            data: data,
            timestamp: data.timestamp,
          }]);
        } catch (e) {
          console.error('Failed to parse action event:', e);
        }
      });

      eventSource.addEventListener('observation', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setAgentEvents(prev => [...prev, {
            type: 'observation',
            data: data,
            timestamp: data.timestamp,
          }]);
        } catch (e) {
          console.error('Failed to parse observation event:', e);
        }
      });

      eventSource.addEventListener('sql_generated', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          setAgentEvents(prev => [...prev, {
            type: 'sql_generated',
            data: data,
            timestamp: data.timestamp,
          }]);
        } catch (e) {
          console.error('Failed to parse sql_generated event:', e);
        }
      });

      eventSource.onerror = (err) => {
        console.error('EventSource error:', err);
        setError('Connection lost. Evaluation may still be running.');
        stopEvaluation();
      };

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [stopEvaluation]);

  const retry = useCallback(() => {
    if (lastConfig) {
      startEvaluation(lastConfig);
    }
  }, [lastConfig, startEvaluation]);

  const clearHistory = useCallback(() => {
    setStatus(null);
    setCurrentTask(null);
    setCompletedTasks([]);
    setAgentEvents([]);
    setCurrentMetrics({});
    setError(null);
    stopEvaluation();
  }, [stopEvaluation]);

  const exportResults = useCallback(async (format: 'submission' | 'detailed' | 'sql_only' | 'metrics') => {
    if (!currentEvaluationId.current) {
      throw new Error('No evaluation to export');
    }

    try {
      const response = await fetch(
        `/api/evaluation/bird-critic/export/${currentEvaluationId.current}/${format}`
      );

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      // Trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bird_critic_${format}_${currentEvaluationId.current}.${format === 'submission' ? 'jsonl' : 'json'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : 'Export failed');
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopEvaluation();
    };
  }, [stopEvaluation]);

  const isRunning = status?.status === 'running';
  const isCompleted = status?.status === 'completed';

  return {
    // Status
    status,
    isRunning,
    isCompleted,

    // Data
    currentTask,
    completedTasks,
    agentEvents,
    currentMetrics,

    // Actions
    startEvaluation,
    stopEvaluation,
    clearHistory,

    // Export
    exportResults,

    // Error handling
    error,
    retry,
  };
}
