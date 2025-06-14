'use client';

import { CheckCircle, XCircle, Loader2, Brain, Search, Database, Lightbulb } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AgentStep } from '@/hooks/useAgentQuery';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

interface AgentProcessingStepsProps {
  steps: AgentStep[];
  isLoading: boolean;
}

export function AgentProcessingSteps({ steps, isLoading }: AgentProcessingStepsProps) {
  const getStepIcon = (step: AgentStep) => {
    if (step.status === 'running') {
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    }

    switch (step.type) {
      case 'thought':
        return <Brain className="h-5 w-5 text-purple-500" />;
      case 'action':
        if (step.metadata?.action_type === 'explore_database') {
          return <Database className="h-5 w-5 text-blue-500" />;
        } else if (step.metadata?.action_type === 'generate_sql') {
          return <Lightbulb className="h-5 w-5 text-yellow-500" />;
        }
        return <Search className="h-5 w-5 text-green-500" />;
      case 'observation':
        return step.status === 'error'
          ? <XCircle className="h-5 w-5 text-red-500" />
          : <CheckCircle className="h-5 w-5 text-green-500" />;
      default:
        return <div className="h-5 w-5 rounded-full border-2 border-muted" />;
    }
  };

  const getStepTitle = (step: AgentStep) => {
    switch (step.type) {
      case 'thought':
        return `Iteration ${step.iteration}: Thinking`;
      case 'action':
        const actionType = step.metadata?.action_type || 'unknown';
        const actionLabels: Record<string, string> = {
          explore_database: 'Exploring Database',
          generate_sql: 'Generating SQL',
          execute_sql: 'Executing Query',
        };
        return `Iteration ${step.iteration}: ${actionLabels[actionType] || actionType}`;
      case 'observation':
        return `Iteration ${step.iteration}: Result`;
      default:
        return `Iteration ${step.iteration}`;
    }
  };

  const formatContent = (step: AgentStep) => {
    if (step.type === 'action' && step.metadata?.parameters?.query) {
      return (
        <div className="space-y-2">
          <p className="text-sm">{step.content}</p>
          <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
            <code>{step.metadata.parameters.query}</code>
          </pre>
        </div>
      );
    }

    if (step.type === 'observation' && step.metadata) {
      const details = [];

      if (step.metadata.row_count !== undefined) {
        details.push(`${step.metadata.row_count} rows`);
      }
      if (step.metadata.columns) {
        details.push(`${step.metadata.columns.length} columns`);
      }
      if (step.metadata.error) {
        details.push(step.metadata.error);
      }

      return (
        <div className="space-y-1">
          <p className="text-sm">{step.content}</p>
          {details.length > 0 && (
            <p className="text-xs text-muted-foreground">{details.join(' • ')}</p>
          )}
        </div>
      );
    }

    return <p className="text-sm">{step.content}</p>;
  };

  const currentIteration = steps.length > 0
    ? Math.max(...steps.map(s => s.iteration))
    : 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isLoading ? (
              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
            ) : steps.some(s => s.status === 'error') ? (
              <XCircle className="h-5 w-5 text-red-500" />
            ) : steps.length > 0 ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <Brain className="h-5 w-5 text-purple-500" />
            )}
            <CardTitle className="text-base">
              {isLoading
                ? `Agent is thinking... (Iteration ${currentIteration})`
                : steps.some(s => s.status === 'error')
                ? 'Agent encountered an issue'
                : steps.length > 0
                ? 'Agent completed successfully'
                : 'Agent ready'
              }
            </CardTitle>
          </div>
          {currentIteration > 0 && (
            <Badge variant="secondary">
              {currentIteration} iteration{currentIteration !== 1 ? 's' : ''}
            </Badge>
          )}
        </div>
      </CardHeader>

      {steps.length > 0 && (
        <CardContent>
          <ScrollArea className="h-[400px] pr-4">
            <div className="space-y-4">
              {steps.map((step, index) => (
                <div
                  key={step.id}
                  className={cn(
                    "flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300",
                    index === steps.length - 1 && isLoading && "opacity-70"
                  )}
                >
                  <div className="flex-shrink-0 pt-0.5">
                    {getStepIcon(step)}
                  </div>
                  <div className="flex-1 min-w-0 space-y-1">
                    <h4 className={cn(
                      "text-sm font-medium",
                      step.type === 'thought' && "text-purple-700 dark:text-purple-400",
                      step.type === 'action' && "text-blue-700 dark:text-blue-400",
                      step.type === 'observation' && step.status === 'error' && "text-red-700 dark:text-red-400",
                      step.type === 'observation' && step.status === 'completed' && "text-green-700 dark:text-green-400"
                    )}>
                      {getStepTitle(step)}
                    </h4>
                    <div className="text-sm text-muted-foreground">
                      {formatContent(step)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      )}
    </Card>
  );
}
