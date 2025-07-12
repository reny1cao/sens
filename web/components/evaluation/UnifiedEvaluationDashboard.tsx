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
  Copy,
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
    copyAnalysisToClipboard,
  } = useUnifiedEvaluation();

  // Local UI state
  const [config, setConfig] = useState<UnifiedEvaluationConfig>(DATASET_CONFIGS['bird-critic'].defaultConfig);
  const [isConfigExpanded, setIsConfigExpanded] = useState(true);
  const [isMetricsExpanded, setIsMetricsExpanded] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);

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

  const handleExport = async (format: 'submission' | 'detailed' | 'sql_only' | 'metrics' | 'analysis') => {
    try {
      setIsExporting(true);
      await exportResults(format);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleCopyAnalysis = async () => {
    try {
      setIsExporting(true);
      const message = await copyAnalysisToClipboard();
      setCopyMessage(message);
      // Clear message after 3 seconds
      setTimeout(() => setCopyMessage(null), 3000);
    } catch (err) {
      console.error('Copy failed:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to copy analysis';
      setCopyMessage(`❌ ${errorMessage}`);
      setTimeout(() => setCopyMessage(null), 5000);
    } finally {
      setIsExporting(false);
    }
  };

  // Connection status indicator - refined
  const ConnectionStatus = () => {
    const statusConfig = {
      connected: { icon: Wifi, color: 'text-emerald-500', bgColor: 'bg-emerald-50 dark:bg-emerald-950/20', label: 'Connected' },
      connecting: { icon: Wifi, color: 'text-amber-500 animate-pulse', bgColor: 'bg-amber-50 dark:bg-amber-950/20', label: 'Connecting' },
      disconnected: { icon: WifiOff, color: 'text-slate-400', bgColor: 'bg-slate-50 dark:bg-slate-950/20', label: 'Disconnected' },
      error: { icon: WifiOff, color: 'text-rose-500', bgColor: 'bg-rose-50 dark:bg-rose-950/20', label: 'Connection Error' },
    };

    const { icon: Icon, color, bgColor, label } = statusConfig[status.connection_status];

    return (
      <div className={`flex items-center gap-3 px-4 py-2 rounded-full ${bgColor} transition-all duration-200`}>
        <Icon className={`h-4 w-4 ${color}`} />
        <span className={`text-sm font-medium ${color}`}>{label}</span>
      </div>
    );
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-6">
      {/* Hero Header - Jony Ive Inspired */}
      <div className="relative overflow-hidden bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 rounded-3xl border border-slate-200/50 dark:border-slate-800/50 shadow-2xl shadow-slate-200/20 dark:shadow-slate-950/40">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-indigo-500/5" />
        <div className="relative px-12 py-16">
          <div className="flex items-center justify-between">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-4">
                <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl shadow-lg shadow-blue-500/25">
                  <Target className="h-8 w-8 text-white" />
                </div>
                <div>
                  <h1 className="text-4xl font-light tracking-tight text-slate-900 dark:text-slate-50">
                    Evaluation Suite
                  </h1>
                  <p className="text-lg text-slate-600 dark:text-slate-400 font-light mt-1">
                    Real-time agent intelligence analysis
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-6">
              <ConnectionStatus />

              <div className="flex items-center gap-3">
                {!isRunning ? (
                  <Button
                    onClick={handleStart}
                    size="lg"
                    className="h-12 px-8 text-base font-medium bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-lg shadow-blue-500/25 transition-all duration-200 border-0"
                  >
                    <Play className="h-5 w-5 mr-3" />
                    Start Evaluation
                  </Button>
                ) : (
                  <Button
                    variant="destructive"
                    onClick={stopEvaluation}
                    size="lg"
                    className="h-12 px-8 text-base font-medium shadow-lg shadow-red-500/25 transition-all duration-200"
                  >
                    <Pause className="h-5 w-5 mr-3" />
                    Stop Evaluation
                  </Button>
                )}

                {(isCompleted || error) && (
                  <Button
                    variant="outline"
                    onClick={resetEvaluation}
                    className="h-12 px-6 border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all duration-200"
                  >
                    <RotateCcw className="h-4 w-4 mr-2" />
                    Reset
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

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

      {/* Configuration Section - Refined */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-lg shadow-slate-200/20 dark:shadow-slate-950/20 overflow-hidden">
        <Collapsible.Root open={isConfigExpanded} onOpenChange={setIsConfigExpanded}>
          <div className="px-8 py-6 border-b border-slate-100 dark:border-slate-800/50">
            <Collapsible.Trigger asChild>
              <Button variant="ghost" className="w-full justify-between p-0 h-auto font-normal hover:bg-transparent">
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-xl">
                    <Settings className="h-5 w-5 text-slate-600 dark:text-slate-400" />
                  </div>
                  <div className="text-left">
                    <h3 className="text-xl font-medium text-slate-900 dark:text-slate-100">Configuration</h3>
                    <Badge variant="secondary" className="mt-1 font-medium">{selectedDataset.label}</Badge>
                  </div>
                </div>
                <div className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                  {isConfigExpanded ? <ChevronUp className="h-5 w-5 text-slate-400" /> : <ChevronDown className="h-5 w-5 text-slate-400" />}
                </div>
              </Button>
            </Collapsible.Trigger>
          </div>

          <Collapsible.Content>
            <div className="px-8 py-8 space-y-8">
              {/* Dataset Selection - Refined */}
              <div>
                <h4 className="text-lg font-medium text-slate-900 dark:text-slate-100 mb-6">Dataset Selection</h4>
                <div className="grid md:grid-cols-2 gap-6">
                  {Object.entries(DATASET_CONFIGS).map(([key, dataset]) => {
                    const Icon = dataset.icon;
                    const isSelected = config.dataset === key;

                    return (
                      <div
                        key={key}
                        className={`relative cursor-pointer rounded-2xl border-2 transition-all duration-300 group ${
                          isSelected
                            ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 shadow-lg shadow-blue-500/20'
                            : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-800/50 hover:shadow-lg hover:shadow-slate-200/20 dark:hover:shadow-slate-950/20'
                        }`}
                        onClick={() => handleDatasetChange(key as keyof typeof DATASET_CONFIGS)}
                      >
                        <div className="p-6">
                          <div className="flex items-start gap-4">
                            <div className={`p-3 rounded-xl transition-colors ${
                              isSelected
                                ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/25'
                                : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 group-hover:bg-slate-200 dark:group-hover:bg-slate-600'
                            }`}>
                              <Icon className="h-6 w-6" />
                            </div>
                            <div className="flex-1">
                              <h3 className={`text-lg font-semibold mb-2 ${
                                isSelected ? 'text-blue-900 dark:text-blue-100' : 'text-slate-900 dark:text-slate-100'
                              }`}>{dataset.label}</h3>
                              <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 leading-relaxed">{dataset.description}</p>
                              <div className="flex flex-wrap gap-2">
                                {dataset.features.map(feature => (
                                  <span key={feature} className={`px-2 py-1 text-xs font-medium rounded-lg ${
                                    isSelected
                                      ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                                      : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
                                  }`}>
                                    {feature}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                        {isSelected && (
                          <div className="absolute top-4 right-4">
                            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Common Configuration - Refined */}
              <div>
                <h4 className="text-lg font-medium text-slate-900 dark:text-slate-100 mb-6">Parameters</h4>
                <div className="grid md:grid-cols-3 gap-6">
                  <div className="space-y-3">
                    <Label htmlFor="limit" className="text-sm font-medium text-slate-700 dark:text-slate-300">Task Limit</Label>
                    <Input
                      id="limit"
                      type="number"
                      value={config.limit?.toString() || ''}
                      onChange={(e) => updateConfig({
                        limit: e.target.value ? parseInt(e.target.value) : undefined
                      })}
                      placeholder="All tasks"
                      disabled={isRunning}
                      className="h-12 border-slate-200 dark:border-slate-700 rounded-xl focus:border-blue-500 focus:ring-blue-500/20 transition-all duration-200"
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400">Leave empty to run all tasks</p>
                  </div>

                  <div className="space-y-3">
                    <Label htmlFor="max_iterations" className="text-sm font-medium text-slate-700 dark:text-slate-300">Max Iterations</Label>
                    <Input
                      id="max_iterations"
                      type="number"
                      value={config.max_iterations.toString()}
                      onChange={(e) => updateConfig({
                        max_iterations: parseInt(e.target.value) || selectedDataset.defaultConfig.max_iterations
                      })}
                      disabled={isRunning}
                      className="h-12 border-slate-200 dark:border-slate-700 rounded-xl focus:border-blue-500 focus:ring-blue-500/20 transition-all duration-200"
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400">Agent reasoning steps per task</p>
                  </div>

                  <div className="space-y-3">
                    <Label htmlFor="debug_mode" className="text-sm font-medium text-slate-700 dark:text-slate-300">Debug Mode</Label>
                    <div className="flex items-center gap-3 h-12">
                      <Switch
                        id="debug_mode"
                        checked={config.debug_mode}
                        onCheckedChange={(checked) => updateConfig({ debug_mode: checked })}
                        disabled={isRunning}
                        className="data-[state=checked]:bg-blue-500"
                      />
                      <span className="text-sm text-slate-600 dark:text-slate-400">
                        {config.debug_mode ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Detailed execution logs</p>
                  </div>
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
            </div>
          </Collapsible.Content>
        </Collapsible.Root>
      </div>

      {/* Status Banner - Refined */}
      {status.status !== 'idle' && (
        <div className="relative overflow-hidden bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-lg shadow-slate-200/20 dark:shadow-slate-950/20">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-blue-500 to-indigo-600"></div>
          <div className="px-8 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-3">
                  {isRunning ? (
                    <div className="relative">
                      <div className="w-4 h-4 bg-blue-500 rounded-full animate-pulse"></div>
                      <div className="absolute inset-0 w-4 h-4 bg-blue-500 rounded-full animate-ping opacity-75"></div>
                    </div>
                  ) : status.status === 'completed' ? (
                    <div className="p-1 bg-emerald-100 dark:bg-emerald-950/30 rounded-full">
                      <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    </div>
                  ) : (
                    <div className="p-1 bg-rose-100 dark:bg-rose-950/30 rounded-full">
                      <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                    </div>
                  )}
                  <span className={`px-3 py-1 text-sm font-medium rounded-full ${
                    status.status === 'completed'
                      ? 'bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'
                      : status.status === 'failed'
                      ? 'bg-rose-100 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300'
                      : 'bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300'
                  }`}>
                    {status.status.charAt(0).toUpperCase() + status.status.slice(1)}
                  </span>
                </div>

                <div className="text-lg font-medium text-slate-900 dark:text-slate-100">
                  {status.completed_tasks} / {status.total_tasks} tasks
                </div>

                {status.start_time && (
                  <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                    <div className="p-1 bg-slate-100 dark:bg-slate-800 rounded">
                      <Clock className="h-3 w-3" />
                    </div>
                    {formatDuration(status.start_time, status.end_time)}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-6">
                <div className="text-right">
                  <div className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                    {status.successful_tasks}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Success</div>
                </div>
                {status.failed_tasks > 0 && (
                  <div className="text-right">
                    <div className="text-lg font-semibold text-rose-600 dark:text-rose-400">
                      {status.failed_tasks}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">Failed</div>
                  </div>
                )}
              </div>
            </div>

            {isRunning && status.total_tasks > 0 && (
              <div className="mt-6">
                <div className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-400 mb-2">
                  <span>Progress</span>
                  <span>{Math.round(progressPercentage)}%</span>
                </div>
                <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${progressPercentage}%` }}
                  ></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Task List - Takes 2/3 width */}
        <div className="lg:col-span-2">
          {(isRunning || completedTasks.length > 0 || status.completed_tasks > 0 || status.status === 'completed') && (
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-lg shadow-slate-200/20 dark:shadow-slate-950/20 overflow-hidden">
              <div className="px-8 py-6 border-b border-slate-100 dark:border-slate-800/50">
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl shadow-lg shadow-purple-500/25">
                    <Brain className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-medium text-slate-900 dark:text-slate-100">Live Evaluation Tasks</h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">Real-time agent intelligence analysis</p>
                  </div>
                </div>
              </div>
              <div className="p-8">
                <UnifiedEvaluationTaskList
                  status={status}
                  currentTask={currentTask}
                  completedTasks={completedTasks}
                  agentEvents={agentEvents}
                  taskEventHistory={taskEventHistory}
                  isRunning={isRunning}
                />
              </div>
            </div>
          )}

          {/* Welcome State - Refined */}
          {status.status === 'idle' && (
            <div className="relative overflow-hidden bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-lg shadow-slate-200/20 dark:shadow-slate-950/20">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5" />
              <div className="relative text-center py-20 px-12">
                <div className="inline-flex p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-3xl shadow-2xl shadow-blue-500/25 mb-8">
                  <Target className="h-12 w-12 text-white" />
                </div>
                <h3 className="text-3xl font-light text-slate-900 dark:text-slate-100 mb-4">
                  Ready to Begin
                </h3>
                <p className="text-lg text-slate-600 dark:text-slate-400 mb-12 max-w-md mx-auto leading-relaxed">
                  Configure your evaluation parameters and start the intelligence analysis.
                </p>
                <div className="grid grid-cols-2 gap-12 max-w-lg mx-auto">
                  <div className="text-center">
                    <div className="text-4xl font-light text-blue-600 dark:text-blue-400 mb-2">530</div>
                    <div className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">BIRD-CRITIC Tasks</div>
                  </div>
                  <div className="text-center">
                    <div className="text-4xl font-light text-emerald-600 dark:text-emerald-400 mb-2">12,751</div>
                    <div className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">BIRD-SQL-DEV Tasks</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Metrics Panel - Refined */}
          {Object.keys(status.metrics).length > 0 && (
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-lg shadow-slate-200/20 dark:shadow-slate-950/20 overflow-hidden">
              <Collapsible.Root open={isMetricsExpanded} onOpenChange={setIsMetricsExpanded}>
                <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-800/50">
                  <Collapsible.Trigger asChild>
                    <Button variant="ghost" className="w-full justify-between p-0 h-auto font-normal hover:bg-transparent">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl shadow-lg shadow-emerald-500/25">
                          <TrendingUp className="h-4 w-4 text-white" />
                        </div>
                        <h3 className="text-lg font-medium text-slate-900 dark:text-slate-100">Metrics</h3>
                      </div>
                      <div className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                        {isMetricsExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                      </div>
                    </Button>
                  </Collapsible.Trigger>
                </div>

                <Collapsible.Content>
                  <div className="p-6 space-y-4">
                    <div className="grid gap-4">
                      <div className="relative overflow-hidden bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 rounded-xl p-6 border border-emerald-200/50 dark:border-emerald-800/50">
                        <div className="text-center">
                          <div className="text-3xl font-light text-emerald-700 dark:text-emerald-300 mb-1">
                            {Math.round((status.metrics.success_rate || status.metrics.execution_success_rate || 0) * 100)}%
                          </div>
                          <div className="text-sm font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Success Rate</div>
                        </div>
                        <div className="absolute top-3 right-3 w-2 h-2 bg-emerald-500 rounded-full"></div>
                      </div>

                      {status.metrics.avg_execution_time_ms && (
                        <div className="relative overflow-hidden bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 rounded-xl p-6 border border-blue-200/50 dark:border-blue-800/50">
                          <div className="text-center">
                            <div className="text-3xl font-light text-blue-700 dark:text-blue-300 mb-1">
                              {Math.round(status.metrics.avg_execution_time_ms)}ms
                            </div>
                            <div className="text-sm font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wider">Avg Time</div>
                          </div>
                          <div className="absolute top-3 right-3 w-2 h-2 bg-blue-500 rounded-full"></div>
                        </div>
                      )}

                      {config.dataset === 'bird-sql-dev' && (
                        <>
                          <div className="relative overflow-hidden bg-gradient-to-br from-purple-50 to-violet-50 dark:from-purple-950/30 dark:to-violet-950/30 rounded-xl p-6 border border-purple-200/50 dark:border-purple-800/50">
                            <div className="text-center">
                              <div className="text-3xl font-light text-purple-700 dark:text-purple-300 mb-1">
                                {Math.round((status.metrics.execution_accuracy || status.metrics.exact_match_rate || 0) * 100)}%
                              </div>
                              <div className="text-sm font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wider">Exact Match</div>
                            </div>
                            <div className="absolute top-3 right-3 w-2 h-2 bg-purple-500 rounded-full"></div>
                          </div>

                          {status.metrics.normalized_match_rate !== undefined && (
                            <div className="relative overflow-hidden bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/30 rounded-xl p-6 border border-amber-200/50 dark:border-amber-800/50">
                              <div className="text-center">
                                <div className="text-3xl font-light text-amber-700 dark:text-amber-300 mb-1">
                                  {Math.round(status.metrics.normalized_match_rate * 100)}%
                                </div>
                                <div className="text-sm font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider">Normalized Match</div>
                              </div>
                              <div className="absolute top-3 right-3 w-2 h-2 bg-amber-500 rounded-full"></div>
                            </div>
                          )}

                          {status.metrics.execution_match_rate !== undefined && (
                            <div className="relative overflow-hidden bg-gradient-to-br from-teal-50 to-cyan-50 dark:from-teal-950/30 dark:to-cyan-950/30 rounded-xl p-6 border border-teal-200/50 dark:border-teal-800/50">
                              <div className="text-center">
                                <div className="text-3xl font-light text-teal-700 dark:text-teal-300 mb-1">
                                  {Math.round(status.metrics.execution_match_rate * 100)}%
                                </div>
                                <div className="text-sm font-medium text-teal-600 dark:text-teal-400 uppercase tracking-wider">Execution Match</div>
                              </div>
                              <div className="absolute top-3 right-3 w-2 h-2 bg-teal-500 rounded-full"></div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </Collapsible.Content>
              </Collapsible.Root>
            </div>
          )}

          {/* Export Panel - Refined */}
          {isCompleted && (
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-lg shadow-slate-200/20 dark:shadow-slate-950/20 overflow-hidden">
              <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-800/50">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-gradient-to-br from-indigo-500 to-blue-600 rounded-xl shadow-lg shadow-indigo-500/25">
                    <Download className="h-4 w-4 text-white" />
                  </div>
                  <h3 className="text-lg font-medium text-slate-900 dark:text-slate-100">Export Results</h3>
                </div>
              </div>
              <div className="p-6 space-y-3">
                {(['detailed', 'submission', 'sql_only', 'metrics', 'analysis'] as const).map(format => {
                  const formatLabels = {
                    detailed: 'Detailed Results',
                    submission: 'Submission Format',
                    sql_only: 'SQL Only',
                    metrics: 'Metrics Summary',
                    analysis: 'Analysis for Claude'
                  };

                  const formatDescriptions = {
                    detailed: 'Complete evaluation data',
                    submission: 'Competition submission format',
                    sql_only: 'Generated SQL queries only',
                    metrics: 'Performance metrics',
                    analysis: 'Comprehensive analysis with thinking steps'
                  };

                  return (
                    <Button
                      key={format}
                      variant="outline"
                      className="w-full justify-start h-16 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all duration-200 rounded-xl text-left"
                      onClick={() => handleExport(format)}
                      disabled={isExporting}
                    >
                      <div className="flex items-center gap-3 w-full">
                        <Download className="h-4 w-4 text-slate-500 flex-shrink-0" />
                        <div className="flex-1">
                          <div className="font-medium text-slate-900 dark:text-slate-100">
                            {formatLabels[format]}
                          </div>
                          <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            {formatDescriptions[format]}
                          </div>
                        </div>
                        {format === 'analysis' && (
                          <div className="px-2 py-1 bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 text-xs font-medium rounded">
                            New
                          </div>
                        )}
                      </div>
                    </Button>
                  );
                })}

                {/* Copy Analysis to Clipboard Button */}
                <div className="pt-3 border-t border-slate-200 dark:border-slate-700">
                  <Button
                    variant="outline"
                    className="w-full justify-start h-14 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all duration-200 rounded-xl text-left border-2 border-dashed"
                    onClick={handleCopyAnalysis}
                    disabled={isExporting}
                  >
                    <div className="flex items-center gap-3 w-full">
                      <Copy className="h-4 w-4 text-slate-500 flex-shrink-0" />
                      <div className="flex-1">
                        <div className="font-medium text-slate-900 dark:text-slate-100">
                          Copy Analysis to Clipboard
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                          Ready to paste into Claude for analysis
                        </div>
                      </div>
                      <div className="px-2 py-1 bg-purple-100 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300 text-xs font-medium rounded">
                        Instant
                      </div>
                    </div>
                  </Button>

                  {/* Copy success message */}
                  {copyMessage && (
                    <div className="mt-2 p-2 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg text-center">
                      <p className="text-sm text-emerald-700 dark:text-emerald-300 font-medium">{copyMessage}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
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
