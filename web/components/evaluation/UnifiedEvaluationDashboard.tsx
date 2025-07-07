/**
 * Unified Evaluation Dashboard - Next Generation
 *
 * Modern, composable evaluation interface that combines the best of all implementations:
 * - Clean hook-based architecture with separation of concerns
 * - Multi-dataset support with type-safe configuration
 * - Robust real-time streaming with race condition prevention
 * - Excellent UX patterns from EvaluationTaskList
 * - Progressive disclosure and responsive design
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import * as Collapsible from '@radix-ui/react-collapsible';
import {
  Play,
  Pause,
  RotateCcw,
  Download,
  Settings,
  Target,
  TrendingUp,
  Brain,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Wifi,
  WifiOff,
  ChevronDown,
  ChevronUp,
  Database,
  Code,
} from 'lucide-react';

import { useUnifiedEvaluation, UnifiedEvaluationConfig } from '@/hooks/useUnifiedEvaluation';
import { UnifiedEvaluationTaskList } from './UnifiedEvaluationTaskList';

// Dataset configuration presets
const DATASET_CONFIGS = {
  'bird-critic': {
    label: 'BIRD-CRITIC',
    description: 'SQL debugging/fixing (PostgreSQL)',
    icon: Code,
    defaultConfig: {
      dataset: 'bird-critic' as const,
      max_iterations: 5,
      debug_mode: true,
      bird_critic_config: {
        database_prefix: 'bird_',
      },
    },
    features: ['SQL Debugging', 'Error Fixing', 'PostgreSQL', 'No Golden SQL'],
  },
  'bird-sql-dev': {
    label: 'BIRD-SQL-DEV',
    description: 'Text-to-SQL generation (SQLite)',
    icon: Database,
    defaultConfig: {
      dataset: 'bird-sql-dev' as const,
      max_iterations: 25,
      debug_mode: true,
      bird_sql_dev_config: {
        dataset_path: 'external/BIRD-SQL-DEV/dev.json',
        database_dir: 'external/BIRD-SQL-DEV/dev_databases',
      },
    },
    features: ['Text-to-SQL', 'Golden SQL', 'SQLite', 'Multi-match Metrics'],
  },
} as const;

export function UnifiedEvaluationDashboard() {
  // Modern hook-based state management
  const {
    status,
    currentTask,
    completedTasks,
    agentEvents,
    taskEventHistory,
    error,
    isRunning,
    isCompleted,
    isConnected,
    progressPercentage,
    startEvaluation,
    stopEvaluation,
    resetEvaluation,
    retryEvaluation,
    exportResults,
  } = useUnifiedEvaluation();

  // Local UI state
  const [config, setConfig] = useState<UnifiedEvaluationConfig>(DATASET_CONFIGS['bird-critic'].defaultConfig);
  const [isConfigExpanded, setIsConfigExpanded] = useState(true);
  const [isMetricsExpanded, setIsMetricsExpanded] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const selectedDataset = DATASET_CONFIGS[config.dataset];

  // Configuration handlers
  const handleDatasetChange = (dataset: keyof typeof DATASET_CONFIGS) => {
    setConfig(DATASET_CONFIGS[dataset].defaultConfig);
  };

  const updateConfig = (updates: Partial<UnifiedEvaluationConfig>) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  // Action handlers
  const handleStart = async () => {
    setIsConfigExpanded(false); // Collapse config when starting
    await startEvaluation(config);
  };

  const handleExport = async (format: 'submission' | 'detailed' | 'sql_only' | 'metrics') => {
    try {
      setIsExporting(true);
      await exportResults(format);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  // Connection status indicator
  const ConnectionStatus = () => {
    const statusConfig = {
      connected: { icon: Wifi, color: 'text-green-500', label: 'Connected' },
      connecting: { icon: Wifi, color: 'text-yellow-500 animate-pulse', label: 'Connecting' },
      disconnected: { icon: WifiOff, color: 'text-gray-400', label: 'Disconnected' },
      error: { icon: WifiOff, color: 'text-red-500', label: 'Connection Error' },
    };

    const { icon: Icon, color, label } = statusConfig[status.connection_status];

    return (
      <div className="flex items-center gap-2 text-sm">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className={color}>{label}</span>
      </div>
    );
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <Card className="border-0 shadow-sm bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                <Target className="h-8 w-8 text-blue-600" />
                Unified Evaluation Suite
              </h1>
              <p className="text-muted-foreground">
                Next-generation evaluation dashboard with real-time agent thinking
              </p>
            </div>

            <div className="flex items-center gap-4">
              <ConnectionStatus />

              <div className="flex items-center gap-3">
                {!isRunning ? (
                  <Button onClick={handleStart} size="lg" className="font-medium">
                    <Play className="h-4 w-4 mr-2" />
                    Start Evaluation
                  </Button>
                ) : (
                  <Button variant="destructive" onClick={stopEvaluation} size="lg">
                    <Pause className="h-4 w-4 mr-2" />
                    Stop Evaluation
                  </Button>
                )}

                {(isCompleted || error) && (
                  <Button variant="outline" onClick={resetEvaluation}>
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Reset
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={retryEvaluation} className="ml-4">
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Configuration Section */}
      <Card>
        <Collapsible.Root open={isConfigExpanded} onOpenChange={setIsConfigExpanded}>
          <CardHeader className="pb-4">
            <Collapsible.Trigger asChild>
              <Button variant="ghost" className="w-full justify-between p-0 h-auto font-normal">
                <div className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  <CardTitle>Evaluation Configuration</CardTitle>
                  <Badge variant="secondary">{selectedDataset.label}</Badge>
                </div>
                {isConfigExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            </Collapsible.Trigger>
          </CardHeader>

          <Collapsible.Content>
            <CardContent className="space-y-6">
              {/* Dataset Selection */}
              <div className="grid md:grid-cols-2 gap-4">
                {Object.entries(DATASET_CONFIGS).map(([key, dataset]) => {
                  const Icon = dataset.icon;
                  const isSelected = config.dataset === key;

                  return (
                    <Card
                      key={key}
                      className={`cursor-pointer transition-all duration-200 ${
                        isSelected
                          ? 'ring-2 ring-blue-500 bg-blue-50 dark:bg-blue-950/20'
                          : 'hover:shadow-md'
                      }`}
                      onClick={() => handleDatasetChange(key as keyof typeof DATASET_CONFIGS)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Icon className={`h-6 w-6 mt-1 ${isSelected ? 'text-blue-600' : 'text-muted-foreground'}`} />
                          <div className="flex-1">
                            <h3 className="font-semibold">{dataset.label}</h3>
                            <p className="text-sm text-muted-foreground mb-2">{dataset.description}</p>
                            <div className="flex flex-wrap gap-1">
                              {dataset.features.map(feature => (
                                <Badge key={feature} variant="outline" className="text-xs">
                                  {feature}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              {/* Common Configuration */}
              <div className="grid md:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="limit">Task Limit (optional)</Label>
                  <Input
                    id="limit"
                    type="number"
                    value={config.limit?.toString() || ''}
                    onChange={(e) => updateConfig({
                      limit: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                    placeholder="All tasks"
                    disabled={isRunning}
                  />
                </div>

                <div>
                  <Label htmlFor="max_iterations">Max Iterations</Label>
                  <Input
                    id="max_iterations"
                    type="number"
                    value={config.max_iterations.toString()}
                    onChange={(e) => updateConfig({
                      max_iterations: parseInt(e.target.value) || selectedDataset.defaultConfig.max_iterations
                    })}
                    disabled={isRunning}
                  />
                </div>

                <div className="flex items-center space-x-2 pt-6">
                  <Switch
                    id="debug_mode"
                    checked={config.debug_mode}
                    onCheckedChange={(checked) => updateConfig({ debug_mode: checked })}
                    disabled={isRunning}
                  />
                  <Label htmlFor="debug_mode">Debug Mode</Label>
                </div>
              </div>

              {/* Dataset-specific Configuration */}
              {config.dataset === 'bird-critic' && (
                <div>
                  <Label htmlFor="database_prefix">Database Prefix</Label>
                  <Input
                    id="database_prefix"
                    value={config.bird_critic_config?.database_prefix || ''}
                    onChange={(e) => updateConfig({
                      bird_critic_config: { database_prefix: e.target.value }
                    })}
                    disabled={isRunning}
                  />
                </div>
              )}

              {config.dataset === 'bird-sql-dev' && (
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="dataset_path">Dataset Path</Label>
                    <Input
                      id="dataset_path"
                      value={config.bird_sql_dev_config?.dataset_path || ''}
                      onChange={(e) => updateConfig({
                        bird_sql_dev_config: {
                          ...config.bird_sql_dev_config,
                          dataset_path: e.target.value
                        }
                      })}
                      disabled={isRunning}
                    />
                  </div>

                  <div>
                    <Label htmlFor="database_dir">Database Directory</Label>
                    <Input
                      id="database_dir"
                      value={config.bird_sql_dev_config?.database_dir || ''}
                      onChange={(e) => updateConfig({
                        bird_sql_dev_config: {
                          ...config.bird_sql_dev_config,
                          database_dir: e.target.value
                        }
                      })}
                      disabled={isRunning}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Collapsible.Content>
        </Collapsible.Root>
      </Card>

      {/* Status Banner */}
      {status.status !== 'idle' && (
        <Card className="border-l-4 border-l-blue-500 bg-gradient-to-r from-blue-50/50 to-transparent dark:from-blue-950/20">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  {isRunning ? (
                    <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
                  ) : status.status === 'completed' ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                  <Badge variant={status.status === 'completed' ? 'default' : status.status === 'failed' ? 'destructive' : 'default'}>
                    {status.status.charAt(0).toUpperCase() + status.status.slice(1)}
                  </Badge>
                </div>

                <div className="text-sm text-muted-foreground">
                  {status.completed_tasks} / {status.total_tasks} tasks
                </div>

                {status.start_time && (
                  <div className="text-sm text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDuration(status.start_time, status.end_time)}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-4">
                <div className="text-sm">
                  <span className="text-green-600 font-medium">{status.successful_tasks}</span> success
                  {status.failed_tasks > 0 && (
                    <>, <span className="text-red-600 font-medium">{status.failed_tasks}</span> failed</>
                  )}
                </div>
              </div>
            </div>

            {isRunning && status.total_tasks > 0 && (
              <div className="mt-3">
                <Progress value={progressPercentage} className="h-2" />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Main Content */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Task List - Takes 2/3 width */}
        <div className="lg:col-span-2">
          {(isRunning || completedTasks.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5" />
                  Live Evaluation Tasks
                </CardTitle>
                <CardDescription>
                  Real-time view of each task with agent thinking steps
                </CardDescription>
              </CardHeader>
              <CardContent>
                <UnifiedEvaluationTaskList
                  status={status}
                  currentTask={currentTask}
                  completedTasks={completedTasks}
                  agentEvents={agentEvents}
                  taskEventHistory={taskEventHistory}
                  isRunning={isRunning}
                />
              </CardContent>
            </Card>
          )}

          {/* Welcome State */}
          {status.status === 'idle' && (
            <Card className="text-center py-12">
              <CardContent>
                <Target className="h-16 w-16 text-blue-500 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">Ready to Start Evaluation</h3>
                <p className="text-muted-foreground mb-6">
                  Configure your evaluation settings and click "Start Evaluation" to begin.
                </p>
                <div className="grid grid-cols-2 gap-8 max-w-md mx-auto">
                  <div>
                    <div className="text-2xl font-bold text-blue-600">530</div>
                    <div className="text-sm text-muted-foreground">BIRD-CRITIC Tasks</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-600">12,751</div>
                    <div className="text-sm text-muted-foreground">BIRD-SQL-DEV Tasks</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Metrics Panel */}
          {Object.keys(status.metrics).length > 0 && (
            <Card>
              <Collapsible.Root open={isMetricsExpanded} onOpenChange={setIsMetricsExpanded}>
                <CardHeader className="pb-4">
                  <Collapsible.Trigger asChild>
                    <Button variant="ghost" className="w-full justify-between p-0 h-auto font-normal">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="h-5 w-5" />
                        <CardTitle>Metrics</CardTitle>
                      </div>
                      {isMetricsExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </Button>
                  </Collapsible.Trigger>
                </CardHeader>

                <Collapsible.Content>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4">
                      <div className="text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">
                          {Math.round((status.metrics.success_rate || 0) * 100)}%
                        </div>
                        <div className="text-sm text-muted-foreground">Success Rate</div>
                      </div>

                      {status.metrics.avg_execution_time_ms && (
                        <div className="text-center p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg">
                          <div className="text-2xl font-bold text-blue-600">
                            {Math.round(status.metrics.avg_execution_time_ms)}ms
                          </div>
                          <div className="text-sm text-muted-foreground">Avg Time</div>
                        </div>
                      )}

                      {config.dataset === 'bird-sql-dev' && status.metrics.execution_accuracy && (
                        <div className="text-center p-3 bg-purple-50 dark:bg-purple-950/20 rounded-lg">
                          <div className="text-2xl font-bold text-purple-600">
                            {Math.round(status.metrics.execution_accuracy * 100)}%
                          </div>
                          <div className="text-sm text-muted-foreground">Execution Accuracy</div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Collapsible.Content>
              </Collapsible.Root>
            </Card>
          )}

          {/* Export Panel */}
          {isCompleted && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Download className="h-5 w-5" />
                  Export Results
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(['detailed', 'submission', 'sql_only', 'metrics'] as const).map(format => (
                  <Button
                    key={format}
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => handleExport(format)}
                    disabled={isExporting}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    {format.charAt(0).toUpperCase() + format.slice(1).replace('_', ' ')}
                  </Button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper function for duration formatting
function formatDuration(start: string, end?: string): string {
  const startTime = new Date(start);
  const endTime = end ? new Date(end) : new Date();
  const duration = Math.floor((endTime.getTime() - startTime.getTime()) / 1000);

  const hours = Math.floor(duration / 3600);
  const minutes = Math.floor((duration % 3600) / 60);
  const seconds = duration % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  } else {
    return `${seconds}s`;
  }
}
