/**
 * Agent Thinking Steps Component
 *
 * Displays real-time agent reasoning steps during BIRD-CRITIC evaluation,
 * similar to the chat interface but optimized for evaluation tasks.
 */

'use client';

import React, { useEffect, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AgentEvent, TaskResult } from '@/hooks/useBirdCriticEvaluation';

interface AgentThinkingStepsProps {
  events: AgentEvent[];
  currentTask: TaskResult | null;
  isRunning: boolean;
}

interface ProcessedStep {
  id: string;
  type: 'thinking' | 'action' | 'observation' | 'sql' | 'answer';
  title: string;
  content: string;
  timestamp: Date;
  success?: boolean;
  metadata?: Record<string, any>;
}

export function AgentThinkingSteps({ events, currentTask, isRunning }: AgentThinkingStepsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Process raw events into structured steps
  const processedSteps: ProcessedStep[] = events.map((event, index) => {
    const timestamp = event.timestamp ? new Date(event.timestamp) : new Date();
    const stepId = `${event.type}-${index}`;

    switch (event.type) {
      case 'reasoning':
      case 'thought':
        return {
          id: stepId,
          type: 'thinking',
          title: `Reasoning Step ${event.data?.iteration || index + 1}`,
          content: event.data?.content || event.data?.reasoning || 'Agent is thinking...',
          timestamp,
          metadata: { iteration: event.data?.iteration },
        };

      case 'action':
        return {
          id: stepId,
          type: 'action',
          title: `Action: ${event.data?.action_type || 'Unknown'}`,
          content: event.data?.reasoning || event.data?.content || 'Executing action...',
          timestamp,
          metadata: {
            action_type: event.data?.action_type,
            parameters: event.data?.parameters,
          },
        };

      case 'observation':
        return {
          id: stepId,
          type: 'observation',
          title: event.data?.success ? 'Success' : 'Failed',
          content: event.data?.error || event.data?.content || 'Action completed',
          timestamp,
          success: event.data?.success,
          metadata: event.data,
        };

      case 'sql_generated':
        return {
          id: stepId,
          type: 'sql',
          title: 'SQL Generated',
          content: event.data?.sql || 'SQL query generated',
          timestamp,
          success: true,
        };

      case 'answer_generated':
        return {
          id: stepId,
          type: 'answer',
          title: 'Answer Provided',
          content: event.data?.answer || event.data?.content || 'Answer generated',
          timestamp,
          success: true,
        };

      default:
        return {
          id: stepId,
          type: 'thinking',
          title: `Event: ${event.type}`,
          content: JSON.stringify(event.data, null, 2),
          timestamp,
        };
    }
  });

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const getStepIcon = (step: ProcessedStep) => {
    switch (step.type) {
      case 'thinking':
        return '🤔';
      case 'action':
        return '🔧';
      case 'observation':
        return step.success === false ? '❌' : '👁️';
      case 'sql':
        return '📝';
      case 'answer':
        return '✅';
      default:
        return '📋';
    }
  };

  const getStepColor = (step: ProcessedStep) => {
    switch (step.type) {
      case 'thinking':
        return 'bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800';
      case 'action':
        return 'bg-purple-50 border-purple-200 dark:bg-purple-950 dark:border-purple-800';
      case 'observation':
        return step.success === false
          ? 'bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800'
          : 'bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800';
      case 'sql':
        return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950 dark:border-yellow-800';
      case 'answer':
        return 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950 dark:border-emerald-800';
      default:
        return 'bg-gray-50 border-gray-200 dark:bg-gray-950 dark:border-gray-800';
    }
  };

  if (!currentTask && events.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <div className="text-4xl mb-2">🤖</div>
        <p>Agent thinking steps will appear here during evaluation</p>
        <p className="text-sm mt-1">Start an evaluation to see real-time reasoning</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Current Task Info */}
      {currentTask && (
        <div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
          <div className="animate-pulse">🧠</div>
          <div>
            <div className="font-medium">Working on Task: {currentTask.task_id}</div>
            <div className="text-sm text-muted-foreground">
              {isRunning ? 'Agent is actively reasoning...' : 'Task completed'}
            </div>
          </div>
        </div>
      )}

      {/* Thinking Steps */}
      <ScrollArea
        className="h-[600px] rounded-md border"
        ref={scrollRef}
      >
        <div className="p-4 space-y-3">
          {processedSteps.map((step, index) => (
            <Card key={step.id} className={`${getStepColor(step)} transition-all duration-200`}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="text-xl flex-shrink-0 mt-0.5">
                    {getStepIcon(step)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="font-medium text-sm">{step.title}</h4>
                      <Badge variant="outline" className="text-xs">
                        {step.timestamp.toLocaleTimeString()}
                      </Badge>
                      {step.metadata?.action_type && (
                        <Badge variant="secondary" className="text-xs">
                          {step.metadata.action_type}
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm">
                      {step.type === 'sql' ? (
                        <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">
                          <code>{step.content}</code>
                        </pre>
                      ) : (
                        <p className="whitespace-pre-wrap break-words">{step.content}</p>
                      )}
                    </div>
                    {step.metadata?.parameters && (
                      <details className="mt-2">
                        <summary className="text-xs text-muted-foreground cursor-pointer hover:underline">
                          Show parameters
                        </summary>
                        <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-x-auto">
                          {JSON.stringify(step.metadata.parameters, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Loading indicator for active evaluation */}
          {isRunning && (
            <Card className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="animate-spin text-xl">⚡</div>
                  <div>
                    <h4 className="font-medium text-sm">Agent Processing...</h4>
                    <p className="text-sm text-muted-foreground">
                      The agent is working on the current task
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </ScrollArea>

      {/* Step Summary */}
      {processedSteps.length > 0 && (
        <div className="flex gap-4 text-sm text-muted-foreground">
          <span>Total Steps: {processedSteps.length}</span>
          <span>Thinking: {processedSteps.filter(s => s.type === 'thinking').length}</span>
          <span>Actions: {processedSteps.filter(s => s.type === 'action').length}</span>
          <span>SQL Generated: {processedSteps.filter(s => s.type === 'sql').length}</span>
        </div>
      )}
    </div>
  );
}
