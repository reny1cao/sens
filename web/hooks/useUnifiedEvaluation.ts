/**
 * Unified Evaluation Hook - Modern Architecture
 *
 * Composable hook system that combines the best patterns from all implementations:
 * - Clean separation of concerns from useBirdCriticEvaluation
 * - Multi-dataset support from ImprovedEvaluationDashboard
 * - Robust event handling and race condition prevention
 * - Type-safe configuration and standardized event formats
 */

import { useCallback, useEffect, useRef, useState } from 'react';

// Unified configuration system
export interface UnifiedEvaluationConfig {
  dataset: 'bird-critic' | 'bird-sql-dev';
  limit?: number;
  debug_mode: boolean;
  max_iterations: number;
  // Dataset-specific configurations
  bird_critic_config?: {
    database_prefix: string;
  };
  bird_sql_dev_config?: {
    dataset_path: string;
    database_dir: string;
  };
}

// Standardized evaluation status
export interface UnifiedEvaluationStatus {
  evaluation_id: string;
  status: 'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'cancelled';
  dataset: string;
  total_tasks: number;
  completed_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  current_task_id?: string;
  start_time?: string;
  end_time?: string;
  metrics: Record<string, any>;
  connection_status: 'disconnected' | 'connecting' | 'connected' | 'error';
}

// Unified task result format
export interface UnifiedTaskResult {
  task_id: string;
  db_id: string;
  query: string;
  generated_sql?: string;
  golden_sql?: string; // Only for datasets that have it
  execution_success: boolean;
  execution_error?: string;
  execution_time_ms?: number;
  result_count?: number;
  difficulty?: string;
  // Dataset-specific fields
  exact_match?: boolean; // BIRD-SQL-DEV
  normalized_match?: boolean; // BIRD-SQL-DEV
  execution_match?: boolean; // BIRD-SQL-DEV
  prompt_flow?: Array<{ model: string; prompt: string; response: string }>; // BIRD-CRITIC
}

// Standardized agent event format
export interface UnifiedAgentEvent {
  type: 'thought' | 'action' | 'observation' | 'sql_generated' | 'answer';
  task_id: string;
  content: string;
  iteration: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

// Hook composition for separation of concerns
export function useUnifiedEvaluation() {
  // Core state management
  const [status, setStatus] = useState<UnifiedEvaluationStatus>({
    evaluation_id: '',
    status: 'idle',
    dataset: '',
    total_tasks: 0,
    completed_tasks: 0,
    successful_tasks: 0,
    failed_tasks: 0,
    metrics: {},
    connection_status: 'disconnected',
  });

  const [currentTask, setCurrentTask] = useState<UnifiedTaskResult | null>(null);
  const [completedTasks, setCompletedTasks] = useState<UnifiedTaskResult[]>([]);
  const [agentEvents, setAgentEvents] = useState<UnifiedAgentEvent[]>([]);
  const [taskEventHistory, setTaskEventHistory] = useState<{[taskId: string]: UnifiedAgentEvent[]}>({});
  const [error, setError] = useState<string | null>(null);

  // Refs for race condition prevention (learned from working implementation)
  const eventSourceRef = useRef<EventSource | null>(null);
  const currentEvaluationIdRef = useRef<string | null>(null);
  const isCompletedRef = useRef<boolean>(false);
  const lastConfigRef = useRef<UnifiedEvaluationConfig | null>(null);

  // Dynamic API endpoint generation (from ImprovedEvaluationDashboard)
  const getApiEndpoint = useCallback((dataset: string, path: string) => {
    return `/api/evaluation/${dataset}${path}`;
  }, []);

  // Clean EventSource cleanup (from working hook pattern)
  const cleanupEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('[UnifiedEvaluation] Cleaning up EventSource');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStatus(prev => ({ ...prev, connection_status: 'disconnected' }));
  }, []);

  // Unified event handler with dataset-aware processing
  const handleAgentEvent = useCallback((event: UnifiedAgentEvent) => {
    setAgentEvents(prev => [...prev, event]);

    // Store in history for persistence (from EvaluationTaskList pattern)
    if (event.task_id) {
      setTaskEventHistory(prev => ({
        ...prev,
        [event.task_id]: [...(prev[event.task_id] || []), event]
      }));
    }
  }, []);

  // Task lifecycle handlers
  const handleTaskStart = useCallback((data: any) => {
    console.log('[UnifiedEvaluation] Task started:', data.task_id);

    const newTask: UnifiedTaskResult = {
      task_id: data.task_id || data.instance_id,
      db_id: data.db_id || '',
      query: data.query || data.question || '',
      execution_success: false,
    };

    setCurrentTask(newTask);
    setAgentEvents([]); // Clear events for new task

    setStatus(prev => ({
      ...prev,
      current_task_id: newTask.task_id,
      completed_tasks: (data.task_number || 1) - 1
    }));
  }, []);

  const handleTaskComplete = useCallback((data: any) => {
    console.log('[UnifiedEvaluation] Task completed:', data.task_id);

    const result: UnifiedTaskResult = {
      task_id: data.task_id || data.instance_id,
      db_id: data.db_id || '',
      query: data.query || data.question || '',
      generated_sql: data.generated_sql || data.sql,
      golden_sql: data.golden_sql,
      execution_success: data.success || data.execution_success || false,
      execution_error: data.error || data.execution_error,
      execution_time_ms: data.execution_time_ms,
      result_count: data.result_count,
      difficulty: data.difficulty,
      exact_match: data.exact_match,
      normalized_match: data.normalized_match,
      execution_match: data.execution_match,
      prompt_flow: data.prompt_flow,
    };

    setCompletedTasks(prev => [...prev, result]);
    setCurrentTask(null);

    // Update counters
    setStatus(prev => ({
      ...prev,
      completed_tasks: prev.completed_tasks + 1,
      successful_tasks: result.execution_success ? prev.successful_tasks + 1 : prev.successful_tasks,
      failed_tasks: result.execution_success ? prev.failed_tasks : prev.failed_tasks + 1,
      current_task_id: undefined,
    }));
  }, []);

  const handleEvaluationComplete = useCallback((data: any) => {
    console.log('[UnifiedEvaluation] Evaluation completed:', data.evaluation_id);

    // Immediately set completion flag to prevent race conditions
    isCompletedRef.current = true;

    setStatus(prev => ({
      ...prev,
      status: 'completed',
      end_time: new Date().toISOString(),
      metrics: data.final_metrics || prev.metrics,
      connection_status: 'disconnected',
    }));

    cleanupEventSource();
  }, [cleanupEventSource]);

  // Streaming setup with robust error handling
  const setupEventStreaming = useCallback((evaluationId: string, dataset: string) => {
    const streamUrl = getApiEndpoint(dataset, `/stream/${evaluationId}`);
    console.log('[UnifiedEvaluation] Setting up EventSource:', streamUrl);

    setStatus(prev => ({ ...prev, connection_status: 'connecting' }));

    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    // Connection management
    eventSource.onopen = () => {
      console.log('[UnifiedEvaluation] EventSource connected');
      setStatus(prev => ({ ...prev, connection_status: 'connected' }));
    };

    // Generic message handler
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'evaluation_start':
            setStatus(prev => ({ ...prev, total_tasks: data.total_tasks }));
            break;
          case 'task_start':
            handleTaskStart(data);
            break;
          case 'task_complete':
            handleTaskComplete(data);
            break;
          case 'metrics_update':
            setStatus(prev => ({ ...prev, metrics: data.metrics }));
            break;
          case 'evaluation_complete':
            handleEvaluationComplete(data);
            break;
          case 'evaluation_error':
          case 'task_error':
            setError(data.error || 'Unknown error');
            break;
        }
      } catch (err) {
        console.error('[UnifiedEvaluation] Failed to parse message:', err);
      }
    };

    // Agent event listeners (from working hook pattern)
    ['thought', 'action', 'observation', 'sql_generated', 'answer'].forEach(eventType => {
      eventSource.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          const agentEvent: UnifiedAgentEvent = {
            type: eventType as any,
            task_id: data.task_id,
            content: data.content,
            iteration: data.iteration || 1,
            timestamp: data.timestamp || new Date().toISOString(),
            metadata: data.metadata,
          };
          handleAgentEvent(agentEvent);
        } catch (err) {
          console.error(`[UnifiedEvaluation] Failed to parse ${eventType} event:`, err);
        }
      });
    });

    // Enhanced error handling with completion detection
    eventSource.onerror = () => {
      console.warn('[UnifiedEvaluation] EventSource error');

      // Prevent restart if evaluation completed (race condition fix)
      if (isCompletedRef.current) {
        console.log('[UnifiedEvaluation] Ignoring error - evaluation completed');
        cleanupEventSource();
        return;
      }

      // Check evaluation status for fast completions
      if (currentEvaluationIdRef.current) {
        fetch(getApiEndpoint(dataset, `/status/${currentEvaluationIdRef.current}`))
          .then(response => response.json())
          .then(statusData => {
            if (statusData.status === 'completed' || statusData.status === 'failed') {
              console.log('[UnifiedEvaluation] Evaluation completed during connection issue');
              handleEvaluationComplete(statusData);
            } else {
              setError('Connection lost. Evaluation may still be running.');
              setStatus(prev => ({ ...prev, connection_status: 'error' }));
            }
          })
          .catch(() => {
            setError('Connection failed');
            setStatus(prev => ({ ...prev, connection_status: 'error' }));
          });
      }

      cleanupEventSource();
    };
  }, [getApiEndpoint, handleTaskStart, handleTaskComplete, handleEvaluationComplete, handleAgentEvent, cleanupEventSource]);

  // Main evaluation start function
  const startEvaluation = useCallback(async (config: UnifiedEvaluationConfig) => {
    try {
      console.log('[UnifiedEvaluation] Starting evaluation:', config);

      // Reset state
      isCompletedRef.current = false;
      lastConfigRef.current = config;
      setError(null);
      setCurrentTask(null);
      setCompletedTasks([]);
      setAgentEvents([]);
      setTaskEventHistory({});

      setStatus(prev => ({
        ...prev,
        status: 'starting',
        dataset: config.dataset,
        total_tasks: 0,
        completed_tasks: 0,
        successful_tasks: 0,
        failed_tasks: 0,
        metrics: {},
        connection_status: 'disconnected',
      }));

      // Clean up any existing connection
      cleanupEventSource();

      // Prepare request config
      const requestConfig = {
        limit: config.limit,
        debug_mode: config.debug_mode,
        max_iterations: config.max_iterations,
        ...(config.dataset === 'bird-critic' && config.bird_critic_config),
        ...(config.dataset === 'bird-sql-dev' && config.bird_sql_dev_config),
      };

      // Start evaluation
      const response = await fetch(getApiEndpoint(config.dataset, '/start'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestConfig),
      });

      if (!response.ok) {
        throw new Error(`Failed to start evaluation: ${response.statusText}`);
      }

      const initialStatus = await response.json();
      currentEvaluationIdRef.current = initialStatus.evaluation_id;

      setStatus(prev => ({
        ...prev,
        evaluation_id: initialStatus.evaluation_id,
        status: 'running',
        start_time: initialStatus.start_time,
        total_tasks: initialStatus.total_tasks,
      }));

      // Start streaming with minimal delay to avoid race conditions
      setTimeout(() => {
        if (currentEvaluationIdRef.current === initialStatus.evaluation_id) {
          setupEventStreaming(initialStatus.evaluation_id, config.dataset);
        }
      }, 100);

    } catch (err) {
      console.error('[UnifiedEvaluation] Failed to start:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      setStatus(prev => ({ ...prev, status: 'failed', connection_status: 'error' }));
    }
  }, [getApiEndpoint, cleanupEventSource, setupEventStreaming]);

  // Stop evaluation
  const stopEvaluation = useCallback(async () => {
    console.log('[UnifiedEvaluation] Stopping evaluation');

    cleanupEventSource();

    if (currentEvaluationIdRef.current && status.dataset) {
      try {
        await fetch(getApiEndpoint(status.dataset, `/${currentEvaluationIdRef.current}`), {
          method: 'DELETE',
        });

        setStatus(prev => ({
          ...prev,
          status: 'cancelled',
          end_time: new Date().toISOString(),
        }));
      } catch (err) {
        console.error('[UnifiedEvaluation] Failed to stop evaluation:', err);
      }
    }

    currentEvaluationIdRef.current = null;
    isCompletedRef.current = false;
  }, [status.dataset, cleanupEventSource, getApiEndpoint]);

  // Reset all state
  const resetEvaluation = useCallback(() => {
    console.log('[UnifiedEvaluation] Resetting evaluation');

    cleanupEventSource();
    currentEvaluationIdRef.current = null;
    isCompletedRef.current = false;
    lastConfigRef.current = null;

    setStatus({
      evaluation_id: '',
      status: 'idle',
      dataset: '',
      total_tasks: 0,
      completed_tasks: 0,
      successful_tasks: 0,
      failed_tasks: 0,
      metrics: {},
      connection_status: 'disconnected',
    });

    setCurrentTask(null);
    setCompletedTasks([]);
    setAgentEvents([]);
    setTaskEventHistory({});
    setError(null);
  }, [cleanupEventSource]);

  // Retry with last config
  const retryEvaluation = useCallback(() => {
    if (lastConfigRef.current) {
      startEvaluation(lastConfigRef.current);
    }
  }, [startEvaluation]);

  // Export functionality
  const exportResults = useCallback(async (format: 'submission' | 'detailed' | 'sql_only' | 'metrics') => {
    if (!currentEvaluationIdRef.current || !status.dataset) {
      throw new Error('No evaluation to export');
    }

    const response = await fetch(
      getApiEndpoint(status.dataset, `/export/${currentEvaluationIdRef.current}/${format}`)
    );

    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `evaluation_${currentEvaluationIdRef.current}_${format}.${format === 'submission' ? 'jsonl' : 'json'}`;
    a.click();
    URL.revokeObjectURL(url);
  }, [status.dataset, getApiEndpoint]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupEventSource();
    };
  }, [cleanupEventSource]);

  // Derived state
  const isRunning = status.status === 'running' || status.status === 'starting';
  const isCompleted = status.status === 'completed';
  const isConnected = status.connection_status === 'connected';
  const progressPercentage = status.total_tasks > 0 ? (status.completed_tasks / status.total_tasks) * 100 : 0;

  return {
    // State
    status,
    currentTask,
    completedTasks,
    agentEvents,
    taskEventHistory,
    error,

    // Derived state
    isRunning,
    isCompleted,
    isConnected,
    progressPercentage,

    // Actions
    startEvaluation,
    stopEvaluation,
    resetEvaluation,
    retryEvaluation,
    exportResults,
  };
}
