/**
 * Evaluation Runs Table Component
 *
 * Displays evaluation runs with expandable task details for each run.
 * Provides better organization and historical tracking of evaluations.
 */

'use client';

import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import * as Collapsible from '@radix-ui/react-collapsible';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import {
  ChevronRight,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  BarChart3,
  Eye,
  Download
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { TaskResult, EvaluationStatus } from '@/hooks/useBirdCriticEvaluation';

interface EvaluationRun {
  id: string;
  status: EvaluationStatus;
  tasks: TaskResult[];
  config: {
    limit?: number;
    max_iterations?: number;
    debug_mode?: boolean;
    database_prefix?: string;
  };
  startTime: Date;
  endTime?: Date;
}

interface EvaluationRunsTableProps {
  currentRun?: {
    status: EvaluationStatus | null;
    tasks: TaskResult[];
    config?: any;
  };
  completedRuns?: EvaluationRun[];
  onExportRun?: (runId: string, format: string) => void;
}

interface TaskDetailDialogProps {
  task: TaskResult;
  trigger: React.ReactNode;
}

function TaskDetailDialog({ task, trigger }: TaskDetailDialogProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        {trigger}
      </DialogTrigger>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Task Details: {task.task_id}</DialogTitle>
          <DialogDescription>
            Detailed information about this evaluation task
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="font-medium text-sm mb-1">Task ID</h4>
              <p className="text-sm text-muted-foreground font-mono">{task.task_id}</p>
            </div>
            <div>
              <h4 className="font-medium text-sm mb-1">Database</h4>
              <Badge variant="outline">{task.db_id}</Badge>
            </div>
            <div>
              <h4 className="font-medium text-sm mb-1">Status</h4>
              <Badge variant={task.success ? 'default' : 'destructive'}>
                {task.success ? 'Success' : 'Failed'}
              </Badge>
            </div>
            <div>
              <h4 className="font-medium text-sm mb-1">Execution Time</h4>
              <p className="text-sm text-muted-foreground">
                {task.execution_time_ms ? `${task.execution_time_ms.toFixed(1)}ms` : 'N/A'}
              </p>
            </div>
          </div>

          {/* Query */}
          <div>
            <h4 className="font-medium text-sm mb-2">Original Query</h4>
            <div className="bg-muted p-3 rounded text-sm">
              {task.query}
            </div>
          </div>

          {/* Generated SQL */}
          {task.sql && (
            <div>
              <h4 className="font-medium text-sm mb-2">Generated SQL</h4>
              <pre className="bg-gray-900 text-gray-100 p-3 rounded text-sm overflow-x-auto">
                <code>{task.sql}</code>
              </pre>
            </div>
          )}

          {/* Error */}
          {task.error && (
            <div>
              <h4 className="font-medium text-sm mb-2 text-red-600">Error Message</h4>
              <div className="bg-red-50 border border-red-200 p-3 rounded text-sm dark:bg-red-950 dark:border-red-800">
                {task.error}
              </div>
            </div>
          )}

          {/* Results Info */}
          {task.result_count !== undefined && (
            <div>
              <h4 className="font-medium text-sm mb-1">Results</h4>
              <p className="text-sm text-muted-foreground">
                {task.result_count} rows returned
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RunTasksTable({ tasks, runId }: { tasks: TaskResult[], runId: string }) {
  const [filter, setFilter] = useState('');

  const filteredTasks = tasks.filter(task =>
    task.task_id.toLowerCase().includes(filter.toLowerCase()) ||
    task.db_id.toLowerCase().includes(filter.toLowerCase()) ||
    task.query.toLowerCase().includes(filter.toLowerCase())
  );

  const formatTime = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms.toFixed(1)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className="space-y-3">
      {/* Task Filter */}
      <Input
        placeholder="Filter tasks..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="max-w-md"
      />

      {/* Tasks Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Task ID</TableHead>
              <TableHead>Database</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Time</TableHead>
              <TableHead>Results</TableHead>
              <TableHead>Query Preview</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTasks.map((task) => (
              <TableRow key={`${runId}-${task.task_id}`}>
                <TableCell className="font-mono text-xs">
                  {task.task_id}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-xs">{task.db_id}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={task.success ? 'default' : 'destructive'} className="text-xs">
                    {task.success ? 'Success' : 'Failed'}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {formatTime(task.execution_time_ms)}
                </TableCell>
                <TableCell className="text-xs">
                  {task.result_count !== undefined ? `${task.result_count} rows` : 'N/A'}
                </TableCell>
                <TableCell className="max-w-xs">
                  <div className="truncate text-xs" title={task.query}>
                    {task.query}
                  </div>
                </TableCell>
                <TableCell>
                  <TaskDetailDialog
                    task={task}
                    trigger={
                      <Button variant="outline" size="sm" className="h-7 px-2 text-xs">
                        <Eye className="w-3 h-3 mr-1" />
                        Details
                      </Button>
                    }
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {filteredTasks.length === 0 && filter && (
        <div className="text-center py-4 text-muted-foreground text-sm">
          No tasks match your filter
        </div>
      )}
    </div>
  );
}

export function EvaluationRunsTable({
  currentRun,
  completedRuns = [],
  onExportRun
}: EvaluationRunsTableProps) {
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState('');

  const toggleRun = (runId: string) => {
    const newExpanded = new Set(expandedRuns);
    if (newExpanded.has(runId)) {
      newExpanded.delete(runId);
    } else {
      newExpanded.add(runId);
    }
    setExpandedRuns(newExpanded);
  };

  // Combine current run with completed runs
  const allRuns: EvaluationRun[] = [];

  // Add current run if exists
  if (currentRun?.status) {
    allRuns.push({
      id: currentRun.status.evaluation_id,
      status: currentRun.status,
      tasks: currentRun.tasks,
      config: currentRun.config || {},
      startTime: new Date(currentRun.status.start_time),
      endTime: currentRun.status.end_time ? new Date(currentRun.status.end_time) : undefined,
    });
  }

  // Add completed runs
  allRuns.push(...completedRuns);

  // Filter runs
  const filteredRuns = allRuns.filter(run =>
    filter === '' ||
    run.id.toLowerCase().includes(filter.toLowerCase()) ||
    run.status.status.toLowerCase().includes(filter.toLowerCase())
  );

  const formatDate = (date: Date) => {
    return date.toLocaleString();
  };

  const getRunDuration = (run: EvaluationRun) => {
    if (!run.endTime) return 'Running...';
    const duration = run.endTime.getTime() - run.startTime.getTime();
    if (duration < 60000) return `${Math.round(duration / 1000)}s`;
    return `${Math.round(duration / 60000)}m ${Math.round((duration % 60000) / 1000)}s`;
  };

  const getRunStats = (run: EvaluationRun) => {
    const total = run.tasks.length;
    const success = run.tasks.filter(t => t.success).length;
    const failed = total - success;
    const successRate = total > 0 ? Math.round((success / total) * 100) : 0;

    return { total, success, failed, successRate };
  };

  if (allRuns.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <div className="text-4xl mb-2">🏃‍♂️</div>
        <p>Evaluation runs will appear here</p>
        <p className="text-sm mt-1">Start an evaluation to see run history</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex gap-4 items-center">
        <Input
          placeholder="Filter by run ID or status..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-md"
        />
        <div className="text-sm text-muted-foreground">
          {filteredRuns.length} run{filteredRuns.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Runs List */}
      <div className="space-y-3">
        {filteredRuns.map((run) => {
          const isExpanded = expandedRuns.has(run.id);
          const isCurrentRun = currentRun?.status?.evaluation_id === run.id;
          const stats = getRunStats(run);

          return (
            <Card key={run.id} className={cn(
              "transition-all duration-200",
              isCurrentRun && "border-blue-200 bg-blue-50/50"
            )}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="p-1 h-8 w-8"
                      onClick={() => toggleRun(run.id)}
                    >
                      <ChevronRight className={cn(
                        "w-4 h-4 transition-transform duration-200",
                        isExpanded && "rotate-90"
                      )} />
                    </Button>

                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle className="text-base font-mono">
                          {run.id.substring(0, 8)}...
                        </CardTitle>
                        {isCurrentRun && (
                          <Badge variant="default" className="text-xs">
                            Current
                          </Badge>
                        )}
                        <Badge
                          variant={
                            run.status.status === 'completed' ? 'default' :
                            run.status.status === 'failed' ? 'destructive' :
                            'secondary'
                          }
                          className="text-xs"
                        >
                          {run.status.status}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(run.startTime)}
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {getRunDuration(run)}
                        </div>
                        <div className="flex items-center gap-1">
                          <BarChart3 className="w-3 h-3" />
                          {stats.total} tasks
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {/* Run Stats */}
                    <div className="flex items-center gap-3 text-sm">
                      <div className="flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4 text-green-600" />
                        <span>{stats.success}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <XCircle className="w-4 h-4 text-red-600" />
                        <span>{stats.failed}</span>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {stats.successRate}% success
                      </Badge>
                    </div>

                    {/* Export Button */}
                    {run.status.status === 'completed' && onExportRun && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onExportRun(run.id, 'detailed')}
                        className="h-8 px-3 text-xs"
                      >
                        <Download className="w-3 h-3 mr-1" />
                        Export
                      </Button>
                    )}
                  </div>
                </div>

                {/* Config Summary */}
                <div className="flex gap-4 text-xs text-muted-foreground">
                  {run.config.limit && (
                    <span>Limit: {run.config.limit}</span>
                  )}
                  {run.config.max_iterations && (
                    <span>Max Iterations: {run.config.max_iterations}</span>
                  )}
                  {run.config.database_prefix && (
                    <span>DB Prefix: {run.config.database_prefix}</span>
                  )}
                  {run.config.debug_mode && (
                    <span>Debug: On</span>
                  )}
                </div>
              </CardHeader>

              {/* Expandable Task Details */}
              <Collapsible.Root open={isExpanded} onOpenChange={() => toggleRun(run.id)}>
                <Collapsible.Content>
                  <CardContent className="pt-0">
                    <div className="border-t pt-4">
                      <h4 className="font-medium text-sm mb-3">
                        Task Details ({run.tasks.length} tasks)
                      </h4>
                      {run.tasks.length > 0 ? (
                        <RunTasksTable tasks={run.tasks} runId={run.id} />
                      ) : (
                        <div className="text-center py-4 text-muted-foreground text-sm">
                          No completed tasks yet
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Collapsible.Content>
              </Collapsible.Root>
            </Card>
          );
        })}
      </div>

      {filteredRuns.length === 0 && filter && (
        <div className="text-center py-4 text-muted-foreground">
          No runs match your filter
        </div>
      )}
    </div>
  );
}
