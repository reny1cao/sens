'use client';

import { CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { ProcessingStep } from '@/types';
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface ProcessingStepsProps {
  steps: ProcessingStep[];
  isLoading: boolean;
}

export function ProcessingSteps({ steps, isLoading }: ProcessingStepsProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Auto-collapse when all steps are completed
  useEffect(() => {
    const allCompleted = steps.every(step => step.status === 'completed');
    if (allCompleted && !isLoading) {
      // Delay collapse to show completion
      const timer = setTimeout(() => setIsCollapsed(true), 1000);
      return () => clearTimeout(timer);
    }
  }, [steps, isLoading]);

  const getStepIcon = (status: ProcessingStep['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'running':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return <div className="h-5 w-5 rounded-full border-2 border-muted" />;
    }
  };

  const getStepDuration = (step: ProcessingStep) => {
    if (step.startTime && step.endTime) {
      const duration = step.endTime - step.startTime;
      return `${(duration / 1000).toFixed(1)}s`;
    }
    return null;
  };

  const completedSteps = steps.filter(s => s.status === 'completed').length;
  const hasError = steps.some(s => s.status === 'error');

  return (
    <Card>
      <CardHeader
        className="cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isLoading ? (
              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
            ) : hasError ? (
              <XCircle className="h-5 w-5 text-red-500" />
            ) : (
              <CheckCircle className="h-5 w-5 text-green-500" />
            )}
            <CardTitle className="text-base">
              {isLoading
                ? `Processing your query... (${completedSteps}/${steps.length} steps)`
                : hasError
                ? 'Query failed'
                : 'Query completed successfully'
              }
            </CardTitle>
          </div>
          <Button variant="ghost" size="sm">
            {isCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>

      {!isCollapsed && (
        <CardContent>
          <div className="space-y-3">
            {steps.map((step) => (
              <div key={step.id} className="flex items-start gap-3">
                <div className="flex-shrink-0 pt-0.5">
                  {getStepIcon(step.status)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className={`text-sm font-medium ${
                      step.status === 'completed' ? 'text-foreground' :
                      step.status === 'error' ? 'text-red-700' :
                      step.status === 'running' ? 'text-blue-700' :
                      'text-muted-foreground'
                    }`}>
                      {step.name}
                    </p>
                    {step.status === 'completed' && (
                      <span className="text-xs text-muted-foreground">
                        {getStepDuration(step)}
                      </span>
                    )}
                  </div>
                  {step.message && (
                    <p className="text-sm text-muted-foreground mt-1">{step.message}</p>
                  )}
                  {step.details && step.status === 'completed' && (
                    <p className="text-xs text-muted-foreground mt-1">{step.details}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
