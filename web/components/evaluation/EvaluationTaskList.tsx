/**
 * Evaluation Task List Component
 *
 * Chat-like interface for BIRD-CRITIC evaluation showing tasks as expandable cards
 * with real-time agent thinking steps, auto-scroll, and auto-collapse when done.
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
  Database
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AgentEvent, TaskResult, EvaluationStatus } from '@/hooks/useBirdCriticEvaluation';

interface TaskWithEvents {
  task_id: string;
  db_id: string;
  query: string;
  status: 'waiting' | 'processing' | 'completed' | 'failed';
  result?: TaskResult;
  events: AgentEvent[];
  allEvents: AgentEvent[]; // Keep all events including from completed tasks
  startTime?: Date;
  endTime?: Date;
}

interface EvaluationTaskListProps {
  status: EvaluationStatus | null;
  currentTask: TaskResult | null;
  completedTasks: TaskResult[];
  agentEvents: AgentEvent[];
  isRunning: boolean;
}

// Transform agent events to chat-compatible format
function transformAgentEvent(event: AgentEvent): any {
  const baseEvent = {
    id: `${event.type}-${event.timestamp || Date.now()}`,
    timestamp: new Date(event.timestamp || Date.now()).getTime(),
    iteration: event.data?.iteration || 1,
  };

  switch (event.type) {
    case 'thought':
    case 'reasoning':
      return {
        ...baseEvent,
        type: 'thought',
        content: event.data?.content || event.data?.reasoning || '',
      };

    case 'action':
      return {
        ...baseEvent,
        type: 'action',
        content: event.data?.content || '',
        metadata: event.data?.metadata,
      };

    case 'observation':
      return {
        ...baseEvent,
        type: 'observation',
        content: event.data?.content || '',
      };

    case 'sql_generated':
      return {
        ...baseEvent,
        type: 'sql',
        content: event.data?.sql || event.data?.content || '',
      };

    default:
      return {
        ...baseEvent,
        type: 'thought',
        content: JSON.stringify(event.data),
      };
  }
}

function getStepIcon(step: any) {
  switch (step.type) {
    case 'thought':
      return <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
        <Sparkles className="w-3 h-3" />
      </div>;
    case 'action':
      return <div className="w-6 h-6 rounded-full bg-purple-100 flex items-center justify-center text-purple-600">
        <Database className="w-3 h-3" />
      </div>;
    case 'observation':
      return <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center text-green-600">
        <CheckCircle2 className="w-3 h-3" />
      </div>;
    case 'sql':
      return <div className="w-6 h-6 rounded-full bg-yellow-100 flex items-center justify-center text-yellow-600">
        <Code2 className="w-3 h-3" />
      </div>;
    default:
      return <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-gray-600">
        <Clock className="w-3 h-3" />
      </div>;
  }
}

export function EvaluationTaskList({
  status,
  currentTask,
  completedTasks,
  agentEvents,
  isRunning
}: EvaluationTaskListProps) {
  const [tasks, setTasks] = useState<TaskWithEvents[]>([]);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [taskEventHistory, setTaskEventHistory] = useState<{[taskId: string]: AgentEvent[]}>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const taskRefs = useRef<{[key: string]: HTMLDivElement | null}>({});

  // Store events for current task in history when it changes
  useEffect(() => {
    if (currentTask) {
      const currentTaskEvents = agentEvents.filter(event =>
        event.data?.task_id === currentTask.task_id
      );

      setTaskEventHistory(prev => ({
        ...prev,
        [currentTask.task_id]: currentTaskEvents
      }));
    }
  }, [currentTask, agentEvents]);

  // Build task list from status and events
  useEffect(() => {
    if (!status) return;

    const newTasks: TaskWithEvents[] = [];

    // Add completed tasks (preserve their event history)
    completedTasks.forEach(task => {
      const storedEvents = taskEventHistory[task.task_id] || [];
      newTasks.push({
        task_id: task.task_id,
        db_id: task.db_id,
        query: task.query,
        status: task.success ? 'completed' : 'failed',
        result: task,
        events: [], // Current events (empty for completed)
        allEvents: storedEvents, // All historical events for this task
        endTime: new Date(),
      });
    });

    // Add current task if exists
    if (currentTask) {
      const currentTaskEvents = agentEvents.filter(event =>
        event.data?.task_id === currentTask.task_id
      );

      newTasks.push({
        task_id: currentTask.task_id,
        db_id: currentTask.db_id,
        query: currentTask.query,
        status: 'processing',
        result: currentTask,
        events: currentTaskEvents, // Live events for current task
        allEvents: currentTaskEvents, // Same as events for current task
        startTime: new Date(),
      });
    }

    // Add waiting tasks (estimate from total_tasks)
    const processedCount = completedTasks.length + (currentTask ? 1 : 0);
    const remainingCount = status.total_tasks - processedCount;

    for (let i = 0; i < remainingCount; i++) {
      newTasks.push({
        task_id: `waiting-${i}`,
        db_id: '',
        query: '',
        status: 'waiting',
        events: [],
        allEvents: [],
      });
    }

    setTasks(newTasks);
  }, [status, currentTask, completedTasks, agentEvents, taskEventHistory]);

  // Auto-expand current task (but don't auto-collapse completed tasks)
  useEffect(() => {
    if (currentTask) {
      setExpandedTask(currentTask.task_id);
    } else if (isRunning && tasks.length > 0) {
      // Find the first processing task
      const processingTask = tasks.find(t => t.status === 'processing');
      if (processingTask) {
        setExpandedTask(processingTask.task_id);
      }
    }
    // Note: We don't auto-collapse completed tasks - let users control manually
  }, [currentTask, isRunning, tasks]);

  // Auto-scroll to current task when events update
  useEffect(() => {
    if (expandedTask && taskRefs.current[expandedTask]) {
      const ref = taskRefs.current[expandedTask];
      if (ref) {
        // Use setTimeout to ensure DOM has updated
        setTimeout(() => {
          ref.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
        }, 100);
      }
    }
  }, [expandedTask, agentEvents, tasks]);

  // Auto-scroll thinking steps container to bottom when new events arrive
  const thinkingStepsRefs = useRef<{[key: string]: HTMLDivElement | null}>({});

  useEffect(() => {
    if (expandedTask && thinkingStepsRefs.current[expandedTask]) {
      const thinkingContainer = thinkingStepsRefs.current[expandedTask];
      if (thinkingContainer) {
        setTimeout(() => {
          thinkingContainer.scrollTop = thinkingContainer.scrollHeight;
        }, 50);
      }
    }
  }, [expandedTask, agentEvents]);

  if (tasks.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <div className="text-4xl mb-2">🚀</div>
        <p>Tasks will appear here during evaluation</p>
        <p className="text-sm mt-1">Start an evaluation to see real-time progress</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[600px] rounded-md border" ref={scrollRef}>
      <div className="p-4 space-y-4">
        {tasks.map((task, index) => {
          const isExpanded = expandedTask === task.task_id;
          const isActive = task.status === 'processing';
          const eventsToShow = isActive ? task.events : task.allEvents; // Show live events for active, historical for completed
          const transformedEvents = eventsToShow.map(transformAgentEvent);
          const hasThinkingSteps = transformedEvents.length > 0;

          return (
            <div
              key={`task-${task.task_id}-${task.status}`} // Stable key that includes status to prevent state loss
              ref={(ref) => { taskRefs.current[task.task_id] = ref; }}
              className={cn(
                "transition-all duration-200",
                isActive && "ring-2 ring-blue-200"
              )}
            >
              <Card className={cn(
                "transition-all duration-200",
                task.status === 'completed' && "border-green-200 bg-green-50/50",
                task.status === 'failed' && "border-red-200 bg-red-50/50",
                task.status === 'processing' && "border-blue-200 bg-blue-50/50",
                task.status === 'waiting' && "border-gray-100 bg-gray-50/50"
              )}>
                <CardContent className="p-4">
                  {/* Task Header */}
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-shrink-0">
                      <div className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center",
                        task.status === 'completed' && "bg-green-100",
                        task.status === 'failed' && "bg-red-100",
                        task.status === 'processing' && "bg-blue-100",
                        task.status === 'waiting' && "bg-gray-100"
                      )}>
                        {task.status === 'processing' ? (
                          <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                        ) : task.status === 'completed' ? (
                          <CheckCircle2 className="w-4 h-4 text-green-600" />
                        ) : task.status === 'failed' ? (
                          <XCircle className="w-4 h-4 text-red-600" />
                        ) : (
                          <Clock className="w-4 h-4 text-gray-600" />
                        )}
                      </div>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          Task {index + 1}
                        </Badge>
                        {task.db_id && (
                          <Badge variant="secondary" className="text-xs">
                            {task.db_id}
                          </Badge>
                        )}
                        <Badge
                          variant={
                            task.status === 'completed' ? 'default' :
                            task.status === 'failed' ? 'destructive' :
                            task.status === 'processing' ? 'default' : 'secondary'
                          }
                          className="text-xs"
                        >
                          {task.status === 'processing' ? 'Analyzing...' : task.status}
                        </Badge>
                        {hasThinkingSteps && task.status !== 'processing' && (
                          <Badge variant="outline" className="text-xs">
                            {transformedEvents.length} steps
                          </Badge>
                        )}
                      </div>

                      {task.query && (
                        <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                          {task.query}
                        </p>
                      )}
                    </div>

                    {/* Expand/Collapse Button - Show for any task with thinking steps */}
                    {hasThinkingSteps && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-2"
                        onClick={() => setExpandedTask(isExpanded ? null : task.task_id)}
                      >
                        <ChevronRight className={cn(
                          "w-4 h-4 transition-transform duration-200",
                          isExpanded && "rotate-90"
                        )} />
                      </Button>
                    )}
                  </div>

                  {/* Thinking Steps - Chat-like expandable */}
                  {hasThinkingSteps && (
                    <Collapsible.Root open={isExpanded} onOpenChange={() =>
                      setExpandedTask(isExpanded ? null : task.task_id)
                    }>
                      <Collapsible.Content className="mt-3">
                        <div
                          className="bg-gray-50/50 rounded-lg p-3 space-y-3 max-h-96 overflow-y-auto"
                          ref={(ref) => { thinkingStepsRefs.current[task.task_id] = ref; }}
                        >
                          {transformedEvents.map((step) => (
                            <div key={step.id} className="flex gap-3">
                              {getStepIcon(step)}
                              <div className="flex-1 min-w-0">
                                <div className={cn(
                                  "text-xs leading-relaxed",
                                  step.type === "action" ? "font-medium text-gray-900" : "text-gray-600"
                                )}>
                                  {step.content}
                                </div>
                                {step.type === "action" && step.metadata?.parameters?.sql && (
                                  <div className="mt-1.5 bg-gray-900 text-gray-100 rounded p-2 font-mono text-[10px] overflow-x-auto">
                                    <code>{step.metadata.parameters.sql}</code>
                                  </div>
                                )}
                                {step.type === "sql" && step.content && (
                                  <div className="mt-1.5 bg-gray-900 text-gray-100 rounded p-2 font-mono text-[10px] overflow-x-auto">
                                    <code>{step.content}</code>
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}

                          {/* Loading indicator for active task */}
                          {isActive && (
                            <div className="flex gap-3 animate-pulse">
                              <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center">
                                <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
                              </div>
                              <div className="flex-1">
                                <div className="text-xs text-blue-600 font-medium">
                                  Agent is thinking...
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </Collapsible.Content>
                    </Collapsible.Root>
                  )}

                  {/* Task Results - Show when completed */}
                  {task.result && task.status !== 'processing' && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>
                          {task.status === 'completed' ? '✅ Completed' : '❌ Failed'}
                        </span>
                        {task.result.execution_time_ms && (
                          <span>{task.result.execution_time_ms}ms</span>
                        )}
                      </div>

                      {task.result.sql && (
                        <details className="mt-2">
                          <summary className="text-xs text-gray-500 cursor-pointer hover:underline">
                            View generated SQL
                          </summary>
                          <div className="mt-1 bg-gray-900 text-gray-100 rounded p-2 font-mono text-[10px] overflow-x-auto">
                            <code>{task.result.sql}</code>
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}
