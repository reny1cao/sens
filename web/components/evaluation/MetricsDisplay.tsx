/**
 * Metrics Display Component
 *
 * Shows real-time evaluation metrics during BIRD-CRITIC evaluation.
 */

'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { EvaluationStatus, TaskResult } from '@/hooks/useBirdCriticEvaluation';

interface MetricsDisplayProps {
  metrics: Record<string, any>;
  status: EvaluationStatus | null;
  completedTasks: TaskResult[];
}

export function MetricsDisplay({ metrics, status, completedTasks }: MetricsDisplayProps) {
  // Calculate real-time metrics from completed tasks if official metrics not available
  const totalTasks = status?.total_tasks || completedTasks.length;
  const successfulTasks = status?.successful_tasks || completedTasks.filter(t => t.success).length;
  const failedTasks = status?.failed_tasks || completedTasks.filter(t => !t.success).length;

  const successRate = totalTasks > 0 ? successfulTasks / totalTasks : 0;
  const sqlGenerationRate = metrics.sql_generation_rate || (
    completedTasks.length > 0 ?
    completedTasks.filter(t => t.sql && t.sql.trim()).length / completedTasks.length : 0
  );

  const avgExecutionTime = metrics.avg_execution_time_ms || (
    completedTasks.length > 0 ?
    completedTasks.reduce((sum, t) => sum + (t.execution_time_ms || 0), 0) / completedTasks.length : 0
  );

  const totalResultCount = metrics.total_result_count ||
    completedTasks.reduce((sum, t) => sum + (t.result_count || 0), 0);

  // Error breakdown
  const errorBreakdown = metrics.error_breakdown || {};
  const errorTypes = Object.entries(errorBreakdown);

  // Submission metrics
  const submissionMetrics = metrics.submission_ready || {
    execution_accuracy: successRate,
    sql_generation_coverage: sqlGenerationRate,
    performance_ms: avgExecutionTime,
  };

  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(1)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  return (
    <div className="space-y-6">
      {/* Main Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <span className="text-2xl">✅</span>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {(successRate * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {successfulTasks} of {totalTasks} tasks
            </p>
            <Progress value={successRate * 100} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">SQL Generation</CardTitle>
            <span className="text-2xl">📝</span>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {(sqlGenerationRate * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              Coverage rate
            </p>
            <Progress value={sqlGenerationRate * 100} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg. Execution Time</CardTitle>
            <span className="text-2xl">⚡</span>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {formatTime(avgExecutionTime)}
            </div>
            <p className="text-xs text-muted-foreground">
              Per task performance
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Results Returned</CardTitle>
            <span className="text-2xl">📊</span>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatNumber(totalResultCount)}
            </div>
            <p className="text-xs text-muted-foreground">
              Total rows retrieved
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Performance Metrics */}
        <Card>
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
            <CardDescription>Task execution and timing statistics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Completed Tasks</span>
                <span className="font-medium">{completedTasks.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Successful Executions</span>
                <span className="font-medium text-green-600">{successfulTasks}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Failed Executions</span>
                <span className="font-medium text-red-600">{failedTasks}</span>
              </div>
              {avgExecutionTime > 0 && (
                <div className="flex justify-between text-sm">
                  <span>Average Time</span>
                  <span className="font-medium">{formatTime(avgExecutionTime)}</span>
                </div>
              )}
              {totalResultCount > 0 && (
                <div className="flex justify-between text-sm">
                  <span>Total Results</span>
                  <span className="font-medium">{formatNumber(totalResultCount)}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Error Analysis */}
        <Card>
          <CardHeader>
            <CardTitle>Error Analysis</CardTitle>
            <CardDescription>Breakdown of failure types</CardDescription>
          </CardHeader>
          <CardContent>
            {errorTypes.length > 0 ? (
              <div className="space-y-3">
                {errorTypes.map(([errorType, count]) => (
                  <div key={errorType} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="capitalize">{errorType.replace('_', ' ')}</span>
                      <Badge variant="destructive">{count}</Badge>
                    </div>
                    <Progress
                      value={failedTasks > 0 ? ((count as number) / failedTasks) * 100 : 0}
                      className="h-2"
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-4 text-muted-foreground">
                {failedTasks === 0 ? (
                  <div>
                    <span className="text-2xl">🎉</span>
                    <p className="mt-2">No errors yet!</p>
                  </div>
                ) : (
                  <p>Error analysis will appear here</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* BIRD-CRITIC Submission Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>BIRD-CRITIC Submission Metrics</CardTitle>
          <CardDescription>
            Official metrics formatted for BIRD-CRITIC submission
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center p-4 bg-muted rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {submissionMetrics.execution_accuracy?.toFixed(3) || '0.000'}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                Execution Accuracy
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Success rate for executed queries
              </div>
            </div>
            <div className="text-center p-4 bg-muted rounded-lg">
              <div className="text-2xl font-bold text-blue-600">
                {submissionMetrics.sql_generation_coverage?.toFixed(3) || '0.000'}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                SQL Generation Coverage
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Percentage of tasks that generated SQL
              </div>
            </div>
            <div className="text-center p-4 bg-muted rounded-lg">
              <div className="text-2xl font-bold text-purple-600">
                {submissionMetrics.performance_ms?.toFixed(1) || '0.0'}ms
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                Performance
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Average execution time per task
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Raw Metrics (for debugging) */}
      {Object.keys(metrics).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Raw Metrics Data</CardTitle>
            <CardDescription>
              Complete metrics object for debugging and analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
              {JSON.stringify(metrics, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
