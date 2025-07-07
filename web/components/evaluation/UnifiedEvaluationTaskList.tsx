/**
 * Unified Evaluation Task List - Next Generation
 *
 * Modern task list component that combines the best UX patterns:
 * - Chat-like interface with auto-scroll and auto-expand
 * - Persistent thinking steps that survive navigation
 * - Unified event handling for all evaluation types
 * - Progressive disclosure and smooth animations
 * - Dataset-agnostic design with flexible event transformation
 */

'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import * as Collapsible from '@radix-ui/react-collapsible';
import {
  Bot,
  ChevronRight,
  Loader2,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Code2,
  Table2,
  Database,
  Zap,
  Eye,
  MessageSquare,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  UnifiedEvaluationStatus,
  UnifiedTaskResult,
  UnifiedAgentEvent
} from '@/hooks/useUnifiedEvaluation';

interface UnifiedTaskWithEvents {
  task_id: string;
  db_id: string;
  query: string;
  status: 'waiting' | 'processing' | 'completed' | 'failed';
  result?: UnifiedTaskResult;
  events: UnifiedAgentEvent[];
  allEvents: UnifiedAgentEvent[]; // Persistent events including from history
  startTime?: Date;
  endTime?: Date;
}

interface UnifiedEvaluationTaskListProps {
  status: UnifiedEvaluationStatus;
  currentTask: UnifiedTaskResult | null;
  completedTasks: UnifiedTaskResult[];
  agentEvents: UnifiedAgentEvent[];
  taskEventHistory: {[taskId: string]: UnifiedAgentEvent[]};
  isRunning: boolean;
}

export function UnifiedEvaluationTaskList({
  status,
  currentTask,
  completedTasks,
  agentEvents,
  taskEventHistory,
  isRunning,
}: UnifiedEvaluationTaskListProps) {
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [tasks, setTasks] = useState<UnifiedTaskWithEvents[]>([]);
  const mainScrollAreaRef = useRef<HTMLDivElement>(null);

  // Keep track of individual task scroll areas for auto-scrolling
  const taskScrollRefs = useRef<{ [taskId: string]: HTMLDivElement | null }>({});

  // Track which tasks we've already scrolled to avoid repeated scrolling
  const scrolledTasksRef = useRef<Set<string>>(new Set());

  // Build unified task list from all data sources
  useEffect(() => {
    const taskMap = new Map<string, UnifiedTaskWithEvents>();

    // Add completed tasks
    completedTasks.forEach(task => {
      const historicalEvents = taskEventHistory[task.task_id] || [];
      taskMap.set(task.task_id, {
        task_id: task.task_id,
        db_id: task.db_id,
        query: task.query,
        status: task.execution_success ? 'completed' : 'failed',
        result: task,
        events: historicalEvents,
        allEvents: historicalEvents,
        startTime: new Date(), // Would be better to track actual times
        endTime: new Date(),
      });
    });

    // Add current task if exists
    if (currentTask) {
      const currentEvents = agentEvents.filter(e => e.task_id === currentTask.task_id);
      const historicalEvents = taskEventHistory[currentTask.task_id] || [];
      const allEvents = [...historicalEvents, ...currentEvents];

      taskMap.set(currentTask.task_id, {
        task_id: currentTask.task_id,
        db_id: currentTask.db_id,
        query: currentTask.query,
        status: 'processing',
        result: currentTask,
        events: currentEvents,
        allEvents: allEvents,
        startTime: new Date(),
      });
    }

    const taskList = Array.from(taskMap.values()).sort((a, b) => {
      // Sort by task order (could improve with actual task numbers)
      return a.task_id.localeCompare(b.task_id);
    });

    setTasks(taskList);

    // Auto-expand current task and auto-collapse completed ones
    if (currentTask) {
      setExpandedTasks(prev => {
        const newExpanded = new Set<string>();
        // Keep current task expanded
        newExpanded.add(currentTask.task_id);
        // Keep any manually expanded completed tasks
        taskList.forEach(task => {
          if (task.status === 'completed' && prev.has(task.task_id)) {
            newExpanded.add(task.task_id);
          }
        });
        return newExpanded;
      });
    }
  }, [currentTask, completedTasks, agentEvents, taskEventHistory]);

  // Auto-scroll main container ONLY when a new task starts (not on every update)
  useEffect(() => {
    if (isRunning && currentTask && mainScrollAreaRef.current) {
      // Check if we haven't scrolled to this task yet
      if (!scrolledTasksRef.current.has(currentTask.task_id)) {
        scrolledTasksRef.current.add(currentTask.task_id);

        // Scroll the main container to show the new task
        requestAnimationFrame(() => {
          if (mainScrollAreaRef.current) {
            mainScrollAreaRef.current.scrollTop = mainScrollAreaRef.current.scrollHeight;
          }
        });
      }
    }
  }, [currentTask, isRunning]);

  // Auto-scroll individual task thinking steps when new events arrive
  useEffect(() => {
    if (currentTask && isRunning && agentEvents.length > 0) {
      const taskId = currentTask.task_id;
      const scrollContainer = taskScrollRefs.current[taskId];

      if (scrollContainer && expandedTasks.has(taskId)) {
        // Use scrollTop instead of scrollIntoView to avoid affecting parent containers
        requestAnimationFrame(() => {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        });
      }
    }
  }, [agentEvents, currentTask, isRunning, expandedTasks]);

  const toggleTaskExpansion = (taskId: string) => {
    setExpandedTasks(prev => {
      const newExpanded = new Set(prev);
      if (newExpanded.has(taskId)) {
        newExpanded.delete(taskId);
      } else {
        newExpanded.add(taskId);
      }
      return newExpanded;
    });
  };

  // Event type icons and styling
  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'thought':
        return <MessageSquare className="h-4 w-4 text-blue-500" />;
      case 'action':
        return <Zap className="h-4 w-4 text-orange-500" />;
      case 'observation':
        return <Eye className="h-4 w-4 text-green-500" />;
      case 'sql_generated':
        return <Code2 className="h-4 w-4 text-purple-500" />;
      case 'answer':
        return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      default:
        return <Bot className="h-4 w-4 text-gray-500" />;
    }
  };

  const getEventTypeLabel = (eventType: string) => {
    switch (eventType) {
      case 'thought':
        return 'Thinking';
      case 'action':
        return 'Action';
      case 'observation':
        return 'Observation';
      case 'sql_generated':
        return 'SQL Generated';
      case 'answer':
        return 'Answer';
      default:
        return eventType.charAt(0).toUpperCase() + eventType.slice(1);
    }
  };

  const TaskCard = ({ task }: { task: UnifiedTaskWithEvents }) => {
    const isExpanded = expandedTasks.has(task.task_id);
    const isProcessing = task.status === 'processing';
    const hasEvents = task.allEvents.length > 0;

    const statusConfig = {
      waiting: { icon: Clock, color: 'text-gray-500', bgColor: 'bg-gray-50', label: 'Waiting' },
      processing: { icon: Loader2, color: 'text-blue-500', bgColor: 'bg-blue-50', label: 'Processing', animate: 'animate-spin' },
      completed: { icon: CheckCircle2, color: 'text-green-500', bgColor: 'bg-green-50', label: 'Completed' },
      failed: { icon: XCircle, color: 'text-red-500', bgColor: 'bg-red-50', label: 'Failed' },
    };

    const { icon: StatusIcon, color, bgColor, label, animate } = statusConfig[task.status];

    return (
      <Card className={cn(
        "transition-all duration-200 border-l-4",
        task.status === 'processing' && "border-l-blue-500 shadow-md",
        task.status === 'completed' && "border-l-green-500",
        task.status === 'failed' && "border-l-red-500",
        task.status === 'waiting' && "border-l-gray-300"
      )}>
        <Collapsible.Root open={isExpanded} onOpenChange={() => toggleTaskExpansion(task.task_id)}>
          <Collapsible.Trigger asChild>
            <CardContent className="p-4 cursor-pointer hover:bg-gray-50/50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <StatusIcon className={cn("h-5 w-5", color, animate)} />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-xs">
                        {task.task_id}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {task.db_id}
                      </Badge>
                      <Badge className={cn("text-xs", bgColor, color)}>
                        {label}
                      </Badge>
                    </div>

                    <p className="text-sm text-muted-foreground">
                      {task.query.length > 100 ? `${task.query.substring(0, 100)}...` : task.query}
                    </p>

                    {task.result && (
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        {task.result.execution_time_ms && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {task.result.execution_time_ms}ms
                          </span>
                        )}
                        {task.result.result_count !== undefined && (
                          <span className="flex items-center gap-1">
                            <Table2 className="h-3 w-3" />
                            {task.result.result_count} rows
                          </span>
                        )}
                        {task.result.exact_match !== undefined && (
                          <span className={cn(
                            "flex items-center gap-1",
                            task.result.exact_match ? "text-green-600" : "text-yellow-600"
                          )}>
                            <Database className="h-3 w-3" />
                            {task.result.exact_match ? "Exact Match" : "Partial Match"}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {hasEvents && (
                    <Badge variant="outline" className="text-xs">
                      {task.allEvents.length} events
                    </Badge>
                  )}
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </div>
            </CardContent>
          </Collapsible.Trigger>

          <Collapsible.Content>
            <CardContent className="px-4 pb-4 pt-0">
              {/* Full Question when expanded */}
              <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-blue-500" />
                  Full Question
                </h4>
                <p className="text-sm whitespace-pre-wrap break-words">{task.query}</p>
              </div>
              {/* Thinking Steps */}
              {task.allEvents.length > 0 && (
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-blue-500" />
                    Agent Thinking Steps
                  </h4>

                  {/* Improved ScrollArea with better height and refs for auto-scroll */}
                  <div
                    ref={(el) => { taskScrollRefs.current[task.task_id] = el; }}
                    className="max-h-[500px] overflow-y-auto relative rounded-lg border bg-gray-50/50 dark:bg-gray-900/30"
                  >
                    <div className="p-4 space-y-3">
                      {task.allEvents.map((event, index) => (
                        <div key={index} className="flex gap-3">
                          <div className="flex-shrink-0 mt-1">
                            {getEventIcon(event.type)}
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-medium text-muted-foreground">
                                {getEventTypeLabel(event.type)}
                              </span>
                              {event.iteration > 1 && (
                                <Badge variant="outline" className="text-xs">
                                  Iteration {event.iteration}
                                </Badge>
                              )}
                              <span className="text-xs text-muted-foreground">
                                {new Date(event.timestamp).toLocaleTimeString()}
                              </span>
                            </div>

                            <div className="text-sm bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm">
                              {event.type === 'sql_generated' ? (
                                <pre className="text-xs overflow-x-auto">
                                  <code className="language-sql">{event.content}</code>
                                </pre>
                              ) : event.type === 'action' && event.metadata ? (
                                <div>
                                  <p className="font-medium text-orange-600 mb-1">
                                    {event.metadata.action_type?.replace(/_/g, ' ').toUpperCase()}
                                  </p>
                                  {event.metadata.parameters && Object.keys(event.metadata.parameters).length > 0 && (
                                    <pre className="text-xs bg-gray-100 dark:bg-gray-700 p-2 rounded mt-1 overflow-x-auto">
                                      {JSON.stringify(event.metadata.parameters, null, 2)}
                                    </pre>
                                  )}
                                  {event.content && (
                                    <p className="text-xs text-muted-foreground mt-1">{event.content}</p>
                                  )}
                                </div>
                              ) : event.type === 'observation' && event.metadata && (event.metadata.rows || event.metadata.row_count !== undefined) ? (
                                <div>
                                  <p className="text-green-600 font-medium mb-2">{event.content}</p>
                                  {event.metadata.rows && event.metadata.rows.length > 0 && (
                                    <div className="mt-2">
                                      <p className="text-xs text-muted-foreground mb-1">Results:</p>
                                      <div className="overflow-x-auto">
                                        <table className="text-xs border-collapse min-w-full">
                                          <thead>
                                            <tr className="border-b">
                                              {Object.keys(event.metadata.rows[0]).map(col => (
                                                <th key={col} className="text-left p-2 font-medium">{col}</th>
                                              ))}
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {event.metadata.rows.slice(0, 5).map((row: any, idx: number) => (
                                              <tr key={idx} className="border-b">
                                                {Object.values(row).map((val: any, colIdx: number) => (
                                                  <td key={colIdx} className="p-2">{String(val)}</td>
                                                ))}
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                        {event.metadata.rows.length > 5 && (
                                          <p className="text-xs text-muted-foreground mt-1">
                                            ... and {event.metadata.rows.length - 5} more rows
                                          </p>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <p className="whitespace-pre-wrap break-words">{event.content}</p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}

                      {/* Live typing indicator for current task */}
                      {isProcessing && task.events.length > 0 && (
                        <div className="flex gap-3 animate-pulse">
                          <div className="flex-shrink-0 mt-1">
                            <Bot className="h-4 w-4 text-blue-500" />
                          </div>
                          <div className="flex-1">
                            <div className="text-xs text-muted-foreground mb-1">Thinking...</div>
                            <div className="flex gap-1">
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                            </div>
                          </div>
                        </div>
                      )}

                    </div>
                  </div>
                </div>
              )}

              {/* Task Results */}
              {task.result && task.status !== 'processing' && (
                <div className="border-t pt-4 mt-4">
                  <h4 className="text-sm font-medium mb-3">Results</h4>

                  <div className="space-y-3">
                    {/* Generated SQL */}
                    {task.result.generated_sql && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Generated SQL</label>
                        <pre className="text-xs bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 overflow-x-auto mt-1">
                          <code>{task.result.generated_sql}</code>
                        </pre>
                      </div>
                    )}

                    {/* Golden SQL (if available) */}
                    {task.result.golden_sql && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Golden SQL</label>
                        <pre className="text-xs bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3 overflow-x-auto mt-1">
                          <code>{task.result.golden_sql}</code>
                        </pre>
                      </div>
                    )}

                    {/* Error (if any) */}
                    {task.result.execution_error && (
                      <div>
                        <label className="text-xs font-medium text-red-600">Error</label>
                        <div className="text-xs bg-red-50 dark:bg-red-900/20 rounded-lg p-3 mt-1">
                          {task.result.execution_error}
                        </div>
                      </div>
                    )}

                    {/* Metrics for BIRD-SQL-DEV */}
                    {(task.result.exact_match !== undefined ||
                      task.result.normalized_match !== undefined ||
                      task.result.execution_match !== undefined) && (
                      <div>
                        <label className="text-xs font-medium text-muted-foreground">Match Metrics</label>
                        <div className="flex gap-2 mt-1">
                          {task.result.exact_match !== undefined && (
                            <Badge variant={task.result.exact_match ? "default" : "secondary"} className="text-xs">
                              Exact: {task.result.exact_match ? "✓" : "✗"}
                            </Badge>
                          )}
                          {task.result.normalized_match !== undefined && (
                            <Badge variant={task.result.normalized_match ? "default" : "secondary"} className="text-xs">
                              Normalized: {task.result.normalized_match ? "✓" : "✗"}
                            </Badge>
                          )}
                          {task.result.execution_match !== undefined && (
                            <Badge variant={task.result.execution_match ? "default" : "secondary"} className="text-xs">
                              Execution: {task.result.execution_match ? "✓" : "✗"}
                            </Badge>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Collapsible.Content>
        </Collapsible.Root>
      </Card>
    );
  };

  if (tasks.length === 0) {
    // Show backend status if available
    if (status.completed_tasks > 0 || status.status === 'completed') {
      return (
        <div className="text-center py-8 text-muted-foreground">
          <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <div>
            <p className="mb-2">Evaluation completed</p>
            <p className="text-sm">
              {status.completed_tasks} task{status.completed_tasks !== 1 ? 's' : ''} completed
              {status.successful_tasks > 0 && ` (${status.successful_tasks} successful)`}
              {status.failed_tasks > 0 && ` (${status.failed_tasks} failed)`}
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="text-center py-8 text-muted-foreground">
        <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No tasks to display. Start an evaluation to see real-time progress.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Main container with improved height */}
      <div
        ref={mainScrollAreaRef}
        className="max-h-[calc(100vh-400px)] overflow-y-auto pr-2 space-y-4"
      >
        {tasks.map(task => (
          <TaskCard key={task.task_id} task={task} />
        ))}
      </div>

      {/* Summary stats */}
      <div className="flex items-center justify-between text-sm text-muted-foreground pt-4 border-t sticky bottom-0 bg-white dark:bg-gray-950">
        <span>
          {tasks.length} task{tasks.length !== 1 ? 's' : ''} total
        </span>
        <div className="flex gap-4">
          <span className="flex items-center gap-1">
            <div className="w-2 h-2 bg-green-500 rounded-full" />
            {tasks.filter(t => t.status === 'completed').length} completed
          </span>
          <span className="flex items-center gap-1">
            <div className="w-2 h-2 bg-blue-500 rounded-full" />
            {tasks.filter(t => t.status === 'processing').length} processing
          </span>
          {tasks.filter(t => t.status === 'failed').length > 0 && (
            <span className="flex items-center gap-1">
              <div className="w-2 h-2 bg-red-500 rounded-full" />
              {tasks.filter(t => t.status === 'failed').length} failed
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
