/**
 * BIRD-CRITIC Evaluation Dashboard
 *
 * Provides a comprehensive interface for running BIRD-CRITIC evaluations
 * with real-time agent thinking steps and metrics display.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EvaluationConfig, useBirdCriticEvaluation } from '@/hooks/useBirdCriticEvaluation';
import { EvaluationTaskList } from './EvaluationTaskList';
import { MetricsDisplay } from './MetricsDisplay';
import { EvaluationRunsTable } from './EvaluationRunsTable';
import { ExportPanel } from './ExportPanel';

export function BirdCriticDashboard() {
  const {
    status,
    isRunning,
    isCompleted,
    currentTask,
    completedTasks,
    agentEvents,
    currentMetrics,
    startEvaluation,
    stopEvaluation,
    clearHistory,
    exportResults,
    error,
    retry,
  } = useBirdCriticEvaluation();

  // Health check state
  const [backendHealth, setBackendHealth] = useState<'checking' | 'ok' | 'error'>('checking');

  // Check backend health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch('/api/health');
        const health = await response.json();
        setBackendHealth(health.backend.status === 'ok' ? 'ok' : 'error');
      } catch {
        setBackendHealth('error');
      }
    };
    checkHealth();
  }, []);

  // Configuration state
  const [config, setConfig] = useState<EvaluationConfig>({
    limit: 5,
    database_prefix: 'bird_',
    debug_mode: true,
    max_iterations: 25,
  });

  const handleConfigChange = (key: keyof EvaluationConfig, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleStart = async () => {
    try {
      console.log('Starting evaluation with config:', config);
      await startEvaluation(config);
    } catch (err) {
      console.error('Failed to start evaluation:', err);
    }
  };

  const progressPercentage = status ? (status.completed_tasks / status.total_tasks) * 100 : 0;

  return (
    <div className="container mx-auto p-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">BIRD-CRITIC Evaluation</h1>
          <div className="text-muted-foreground flex items-center gap-2">
            Agent-based text-to-SQL evaluation with real-time thinking steps
            <Badge
              variant={backendHealth === 'ok' ? 'default' : backendHealth === 'error' ? 'destructive' : 'secondary'}
              className="text-xs"
            >
              {backendHealth === 'checking' ? '🔄 Checking...' :
               backendHealth === 'ok' ? '✅ Backend Connected' :
               '❌ Backend Offline'}
            </Badge>
          </div>
        </div>
        <div className="flex gap-2">
          {isCompleted && (
            <Button variant="outline" onClick={clearHistory}>
              Clear History
            </Button>
          )}
          {isRunning && (
            <Button variant="destructive" onClick={stopEvaluation}>
              Stop Evaluation
            </Button>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription className="flex items-center gap-2">
            {error}
            <Button variant="outline" size="sm" onClick={retry}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Configuration Panel */}
      {!isRunning && (
        <Card>
          <CardHeader>
            <CardTitle>Evaluation Configuration</CardTitle>
            <CardDescription>
              Configure the parameters for your BIRD-CRITIC evaluation run
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="limit">Task Limit</Label>
                <Input
                  id="limit"
                  type="number"
                  value={config.limit || ''}
                  onChange={(e) => {
                    const value = e.target.value;
                    const numValue = value ? parseInt(value) : undefined;
                    console.log('Task limit changed:', value, '->', numValue);
                    handleConfigChange('limit', numValue);
                  }}
                  placeholder="Leave empty for all tasks"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max_iterations">Max Agent Iterations</Label>
                <Input
                  id="max_iterations"
                  type="number"
                  value={config.max_iterations || 25}
                  onChange={(e) => handleConfigChange('max_iterations', parseInt(e.target.value))}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="database_prefix">Database Prefix</Label>
                <Input
                  id="database_prefix"
                  value={config.database_prefix || 'bird_'}
                  onChange={(e) => handleConfigChange('database_prefix', e.target.value)}
                />
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="debug_mode"
                  checked={config.debug_mode || false}
                  onCheckedChange={(checked) => handleConfigChange('debug_mode', checked)}
                />
                <Label htmlFor="debug_mode">Debug Mode (Verbose Logging)</Label>
              </div>
            </div>
            <Button
              onClick={handleStart}
              disabled={backendHealth !== 'ok'}
              className="w-full"
            >
              {backendHealth === 'checking' ? 'Checking Backend...' :
               backendHealth === 'error' ? 'Backend Offline' :
               'Start Evaluation'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Status Display */}
      {status && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Evaluation Status
              <Badge variant={
                status.status === 'running' ? 'default' :
                status.status === 'completed' ? 'secondary' : 'destructive'
              }>
                {status.status.charAt(0).toUpperCase() + status.status.slice(1)}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <span>{status.completed_tasks} / {status.total_tasks} tasks</span>
              </div>
              <Progress value={progressPercentage} className="w-full" />
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Successful: </span>
                <span className="text-green-600">{status.successful_tasks}</span>
              </div>
              <div>
                <span className="font-medium">Failed: </span>
                <span className="text-red-600">{status.failed_tasks}</span>
              </div>
            </div>
            {status.current_task && (
              <div className="text-sm">
                <span className="font-medium">Current Task: </span>
                <code className="bg-muted px-1 py-0.5 rounded">{status.current_task}</code>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Main Content Tabs */}
      {(isRunning || isCompleted) && (
        <Tabs defaultValue="thinking" className="space-y-4">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="thinking">Agent Thinking</TabsTrigger>
            <TabsTrigger value="metrics">Live Metrics</TabsTrigger>
            <TabsTrigger value="results">Task Results</TabsTrigger>
            <TabsTrigger value="export">Export</TabsTrigger>
          </TabsList>

          <TabsContent value="thinking" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Evaluation Tasks</CardTitle>
                <CardDescription>
                  Real-time view of each task with agent thinking steps and results
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EvaluationTaskList
                  status={status}
                  currentTask={currentTask}
                  completedTasks={completedTasks}
                  agentEvents={agentEvents}
                  isRunning={isRunning}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="metrics" className="space-y-4">
            <MetricsDisplay
              metrics={currentMetrics}
              status={status}
              completedTasks={completedTasks}
            />
          </TabsContent>

          <TabsContent value="results" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Evaluation Runs</CardTitle>
                <CardDescription>
                  Historical view of evaluation runs with detailed task results
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EvaluationRunsTable
                  currentRun={status ? {
                    status,
                    tasks: completedTasks,
                    config: {
                      limit: config.limit,
                      max_iterations: config.max_iterations,
                      debug_mode: config.debug_mode,
                      database_prefix: config.database_prefix,
                    }
                  } : undefined}
                  onExportRun={(runId, format) => {
                    if (status?.evaluation_id === runId) {
                      exportResults(format as any);
                    }
                  }}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="export" className="space-y-4">
            <ExportPanel
              onExport={exportResults}
              isCompleted={isCompleted}
              evaluationId={status?.evaluation_id}
              metrics={currentMetrics}
            />
          </TabsContent>
        </Tabs>
      )}

      {/* Quick Stats */}
      {!isRunning && !status && (
        <Card>
          <CardHeader>
            <CardTitle>About BIRD-CRITIC Evaluation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              BIRD-CRITIC is a benchmark for evaluating text-to-SQL systems on challenging real-world queries.
              This interface allows you to run evaluations with our agent-based system and see real-time thinking steps.
            </p>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-3 bg-muted rounded-lg">
                <div className="text-2xl font-bold">530</div>
                <div className="text-xs text-muted-foreground">Total Tasks</div>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <div className="text-2xl font-bold">15</div>
                <div className="text-xs text-muted-foreground">Databases</div>
              </div>
              <div className="p-3 bg-muted rounded-lg">
                <div className="text-2xl font-bold">~5min</div>
                <div className="text-xs text-muted-foreground">Est. Runtime (5 tasks)</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
