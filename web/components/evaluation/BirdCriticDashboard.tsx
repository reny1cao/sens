/**
 * BIRD-CRITIC Evaluation Dashboard
 *
 * Provides a comprehensive interface for running BIRD-CRITIC evaluations
 * with real-time agent thinking steps and metrics display.
 *
 * Refined with Jony Ive-inspired design principles:
 * - Clean, purposeful visual hierarchy
 * - Elegant material design with subtle depth
 * - Thoughtful use of space and typography
 */

"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  EvaluationConfig,
  useBirdCriticEvaluation,
} from "@/hooks/useBirdCriticEvaluation";
import { EvaluationTaskList } from "./EvaluationTaskList";
import { MetricsDisplay } from "./MetricsDisplay";
import { EvaluationRunsTable } from "./EvaluationRunsTable";
import { ExportPanel } from "./ExportPanel";

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
  const [backendHealth, setBackendHealth] = useState<
    "checking" | "ok" | "error"
  >("checking");

  // Check backend health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch("/api/health");
        const health = await response.json();
        setBackendHealth(health.backend.status === "ok" ? "ok" : "error");
      } catch {
        setBackendHealth("error");
      }
    };
    checkHealth();
  }, []);

  // Configuration state
  const [config, setConfig] = useState<EvaluationConfig>({
    limit: 5,
    database_prefix: "bird_",
    debug_mode: true,
    max_iterations: 25,
  });

  const handleConfigChange = (key: keyof EvaluationConfig, value: any) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleStart = async () => {
    try {
      console.log("Starting evaluation with config:", config);
      await startEvaluation(config);
    } catch (err) {
      console.error("Failed to start evaluation:", err);
    }
  };

  const progressPercentage = status
    ? (status.completed_tasks / status.total_tasks) * 100
    : 0;

  // Health status indicator component
  const HealthIndicator = () => {
    const getHealthConfig = () => {
      switch (backendHealth) {
        case "ok":
          return {
            icon: "●",
            text: "Connected",
            className:
              "text-emerald-500 bg-emerald-50 border-emerald-200 dark:bg-emerald-950 dark:border-emerald-800",
          };
        case "error":
          return {
            icon: "●",
            text: "Disconnected",
            className:
              "text-red-500 bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800",
          };
        default:
          return {
            icon: "○",
            text: "Checking",
            className:
              "text-gray-500 bg-gray-50 border-gray-200 dark:bg-gray-950 dark:border-gray-800",
          };
      }
    };

    const health = getHealthConfig();

    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${health.className} transition-all duration-300 ease-in-out`}
      >
        <span className="animate-pulse">{health.icon}</span>
        {health.text}
      </div>
    );
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-8">
      {/* Refined Header with better typography hierarchy */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl font-light tracking-tight text-gray-900 dark:text-gray-100">
              BIRD-CRITIC
            </h1>
            <div className="flex items-center gap-3 text-gray-600 dark:text-gray-400">
              <p className="text-sm font-medium">
                Agent-based text-to-SQL evaluation with real-time reasoning
              </p>
              <HealthIndicator />
            </div>
          </div>
          <div className="flex gap-3">
            {isCompleted && (
              <Button
                variant="outline"
                onClick={clearHistory}
                className="transition-all duration-200 ease-in-out hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Clear History
              </Button>
            )}
            {isRunning && (
              <Button
                variant="destructive"
                onClick={stopEvaluation}
                className="transition-all duration-200 ease-in-out"
              >
                Stop Evaluation
              </Button>
            )}
          </div>
        </div>

        {/* Elegant error display */}
        {error && (
          <Alert className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
            <AlertDescription className="flex items-center justify-between">
              <span className="text-red-800 dark:text-red-200">{error}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={retry}
                className="ml-4 text-red-700 border-red-300 hover:bg-red-100 dark:text-red-300 dark:border-red-700 dark:hover:bg-red-900"
              >
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Refined Configuration Panel */}
      {!isRunning && (
        <Card className="border-0 shadow-sm bg-white/70 dark:bg-gray-900/70 backdrop-blur-sm">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg font-medium text-gray-900 dark:text-gray-100">
              Evaluation Configuration
            </CardTitle>
            <CardDescription className="text-gray-600 dark:text-gray-400">
              Configure the parameters for your evaluation run
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <Label
                  htmlFor="limit"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Task Limit
                </Label>
                <Input
                  id="limit"
                  type="number"
                  value={config.limit || ""}
                  onChange={(e) => {
                    const value = e.target.value;
                    const numValue = value ? parseInt(value) : undefined;
                    handleConfigChange("limit", numValue);
                  }}
                  placeholder="Leave empty for all tasks"
                  className="border-gray-200 dark:border-gray-700 focus:border-blue-500 dark:focus:border-blue-400 transition-colors duration-200 ease-in-out"
                />
              </div>
              <div className="space-y-3">
                <Label
                  htmlFor="max_iterations"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Max Agent Iterations
                </Label>
                <Input
                  id="max_iterations"
                  type="number"
                  value={config.max_iterations || 25}
                  onChange={(e) =>
                    handleConfigChange(
                      "max_iterations",
                      parseInt(e.target.value)
                    )
                  }
                  className="border-gray-200 dark:border-gray-700 focus:border-blue-500 dark:focus:border-blue-400 transition-colors duration-200 ease-in-out"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <Label
                  htmlFor="database_prefix"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Database Prefix
                </Label>
                <Input
                  id="database_prefix"
                  value={config.database_prefix || "bird_"}
                  onChange={(e) =>
                    handleConfigChange("database_prefix", e.target.value)
                  }
                  className="border-gray-200 dark:border-gray-700 focus:border-blue-500 dark:focus:border-blue-400 transition-colors duration-200 ease-in-out"
                />
              </div>
              <div className="flex items-center space-x-3 pt-6">
                <Switch
                  id="debug_mode"
                  checked={config.debug_mode || false}
                  onCheckedChange={(checked) =>
                    handleConfigChange("debug_mode", checked)
                  }
                />
                <Label
                  htmlFor="debug_mode"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Debug Mode (Verbose Logging)
                </Label>
              </div>
            </div>
            <Button
              onClick={handleStart}
              disabled={backendHealth !== "ok"}
              className="w-full h-11 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 transition-all duration-200 ease-in-out font-medium"
            >
              {backendHealth === "checking"
                ? "Checking Backend..."
                : backendHealth === "error"
                ? "Backend Offline"
                : "Start Evaluation"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Elegant Status Display */}
      {status && (
        <Card className="border-0 shadow-sm bg-white/70 dark:bg-gray-900/70 backdrop-blur-sm">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-3 text-lg font-medium">
              Evaluation Status
              <Badge
                variant="secondary"
                className={`
                  ${
                    status.status === "running"
                      ? "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800"
                      : status.status === "completed"
                      ? "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800"
                      : "bg-red-100 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800"
                  }
                  border transition-all duration-200 ease-in-out
                `}
              >
                {status.status.charAt(0).toUpperCase() + status.status.slice(1)}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">Progress</span>
                <span className="font-mono">
                  {status.completed_tasks} / {status.total_tasks} tasks
                </span>
              </div>
              <Progress
                value={progressPercentage}
                className="h-2 bg-gray-100 dark:bg-gray-800"
              />
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div className="text-center p-4 rounded-lg bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800">
                <div className="text-2xl font-light text-emerald-700 dark:text-emerald-300">
                  {status.successful_tasks}
                </div>
                <div className="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wide">
                  Successful
                </div>
              </div>
              <div className="text-center p-4 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800">
                <div className="text-2xl font-light text-red-700 dark:text-red-300">
                  {status.failed_tasks}
                </div>
                <div className="text-xs font-medium text-red-600 dark:text-red-400 uppercase tracking-wide">
                  Failed
                </div>
              </div>
            </div>
            {status.current_task && (
              <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
                <div className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1">
                  Current Task
                </div>
                <code className="text-xs text-blue-600 dark:text-blue-400 font-mono">
                  {status.current_task}
                </code>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Refined Main Content Tabs */}
      {(isRunning || isCompleted) && (
        <Tabs defaultValue="thinking" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
            <TabsTrigger
              value="thinking"
              className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-700 data-[state=active]:shadow-sm transition-all duration-200 ease-in-out"
            >
              Agent Thinking
            </TabsTrigger>
            <TabsTrigger
              value="metrics"
              className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-700 data-[state=active]:shadow-sm transition-all duration-200 ease-in-out"
            >
              Live Metrics
            </TabsTrigger>
            <TabsTrigger
              value="results"
              className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-700 data-[state=active]:shadow-sm transition-all duration-200 ease-in-out"
            >
              Task Results
            </TabsTrigger>
            <TabsTrigger
              value="export"
              className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-700 data-[state=active]:shadow-sm transition-all duration-200 ease-in-out"
            >
              Export
            </TabsTrigger>
          </TabsList>

          <TabsContent value="thinking" className="space-y-6">
            <Card className="border-0 shadow-sm bg-white/70 dark:bg-gray-900/70 backdrop-blur-sm">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-medium">
                  Evaluation Tasks
                </CardTitle>
                <CardDescription>
                  Real-time view of each task with agent thinking steps and
                  results
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

          <TabsContent value="metrics" className="space-y-6">
            <MetricsDisplay
              metrics={currentMetrics}
              status={status}
              completedTasks={completedTasks}
            />
          </TabsContent>

          <TabsContent value="results" className="space-y-6">
            <Card className="border-0 shadow-sm bg-white/70 dark:bg-gray-900/70 backdrop-blur-sm">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-medium">
                  Evaluation Runs
                </CardTitle>
                <CardDescription>
                  Historical view of evaluation runs with detailed task results
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EvaluationRunsTable
                  currentRun={
                    status
                      ? {
                          status,
                          tasks: completedTasks,
                          config: {
                            limit: config.limit,
                            max_iterations: config.max_iterations,
                            debug_mode: config.debug_mode,
                            database_prefix: config.database_prefix,
                          },
                        }
                      : undefined
                  }
                  onExportRun={(runId, format) => {
                    if (status?.evaluation_id === runId) {
                      exportResults(format as any);
                    }
                  }}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="export" className="space-y-6">
            <ExportPanel
              onExport={exportResults}
              isCompleted={isCompleted}
              evaluationId={status?.evaluation_id}
              metrics={currentMetrics}
            />
          </TabsContent>
        </Tabs>
      )}

      {/* Refined Welcome State */}
      {!isRunning && !status && (
        <Card className="border-0 shadow-sm bg-white/70 dark:bg-gray-900/70 backdrop-blur-sm">
          <CardHeader className="pb-6">
            <CardTitle className="text-lg font-medium text-center">
              About BIRD-CRITIC Evaluation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-center text-gray-600 dark:text-gray-400 max-w-2xl mx-auto leading-relaxed">
              BIRD-CRITIC is a benchmark for evaluating text-to-SQL systems on
              challenging real-world queries. This interface allows you to run
              evaluations with our agent-based system and observe real-time
              thinking steps.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center p-6 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 border border-blue-100 dark:border-blue-800">
                <div className="text-3xl font-light text-blue-600 dark:text-blue-400 mb-2">
                  530
                </div>
                <div className="text-sm font-medium text-blue-700 dark:text-blue-300 uppercase tracking-wide">
                  Total Tasks
                </div>
              </div>
              <div className="text-center p-6 rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950 border border-emerald-100 dark:border-emerald-800">
                <div className="text-3xl font-light text-emerald-600 dark:text-emerald-400 mb-2">
                  15
                </div>
                <div className="text-sm font-medium text-emerald-700 dark:text-emerald-300 uppercase tracking-wide">
                  Databases
                </div>
              </div>
              <div className="text-center p-6 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950 dark:to-orange-950 border border-amber-100 dark:border-amber-800">
                <div className="text-3xl font-light text-amber-600 dark:text-amber-400 mb-2">
                  ~5min
                </div>
                <div className="text-sm font-medium text-amber-700 dark:text-amber-300 uppercase tracking-wide">
                  Est. Runtime (5 tasks)
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
