/**
 * Task Results Table Component
 *
 * Displays detailed results for each completed BIRD-CRITIC evaluation task.
 */

'use client';

import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { TaskResult } from '@/hooks/useBirdCriticEvaluation';

interface TaskResultsTableProps {
  results: TaskResult[];
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
              <p className="text-sm text-muted-foreground">{task.task_id}</p>
            </div>
            <div>
              <h4 className="font-medium text-sm mb-1">Database</h4>
              <p className="text-sm text-muted-foreground">{task.db_id}</p>
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
              <pre className="bg-muted p-3 rounded text-sm overflow-x-auto">
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

          {/* Prompt Flow */}
          {task.prompt_flow && task.prompt_flow.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-2">Prompt Flow</h4>
              <div className="space-y-3 max-h-60 overflow-y-auto">
                {task.prompt_flow.map((step, index) => (
                  <div key={index} className="bg-muted p-3 rounded">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline" className="text-xs">
                        Step {index + 1}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {step.model}
                      </Badge>
                    </div>
                    <div className="text-xs space-y-2">
                      <div>
                        <strong>Prompt:</strong>
                        <p className="mt-1 text-muted-foreground">{step.prompt}</p>
                      </div>
                      {step.response && (
                        <div>
                          <strong>Response:</strong>
                          <p className="mt-1 text-muted-foreground">{step.response}</p>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function TaskResultsTable({ results }: TaskResultsTableProps) {
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'failed'>('all');

  // Filter results
  const filteredResults = results.filter(result => {
    const matchesFilter = filter === '' ||
      result.task_id.toLowerCase().includes(filter.toLowerCase()) ||
      result.db_id.toLowerCase().includes(filter.toLowerCase()) ||
      result.query.toLowerCase().includes(filter.toLowerCase());

    const matchesStatus = statusFilter === 'all' ||
      (statusFilter === 'success' && result.success) ||
      (statusFilter === 'failed' && !result.success);

    return matchesFilter && matchesStatus;
  });

  const formatTime = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms.toFixed(1)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  if (results.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <div className="text-4xl mb-2">📊</div>
        <p>Task results will appear here as evaluation progresses</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-4 items-center">
        <Input
          placeholder="Filter by task ID, database, or query..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-md"
        />
        <div className="flex gap-2">
          <Button
            variant={statusFilter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter('all')}
          >
            All ({results.length})
          </Button>
          <Button
            variant={statusFilter === 'success' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter('success')}
          >
            Success ({results.filter(r => r.success).length})
          </Button>
          <Button
            variant={statusFilter === 'failed' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter('failed')}
          >
            Failed ({results.filter(r => !r.success).length})
          </Button>
        </div>
      </div>

      {/* Results Summary */}
      <div className="text-sm text-muted-foreground">
        Showing {filteredResults.length} of {results.length} tasks
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Task ID</TableHead>
              <TableHead>Database</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Execution Time</TableHead>
              <TableHead>Results</TableHead>
              <TableHead>Query Preview</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredResults.map((result) => (
              <TableRow key={result.task_id}>
                <TableCell className="font-mono text-sm">
                  {result.task_id}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{result.db_id}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={result.success ? 'default' : 'destructive'}>
                    {result.success ? 'Success' : 'Failed'}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-sm">
                  {formatTime(result.execution_time_ms)}
                </TableCell>
                <TableCell>
                  {result.result_count !== undefined ? (
                    <span className="text-sm">{result.result_count} rows</span>
                  ) : (
                    <span className="text-muted-foreground">N/A</span>
                  )}
                </TableCell>
                <TableCell className="max-w-xs">
                  <div className="truncate text-sm" title={result.query}>
                    {result.query}
                  </div>
                </TableCell>
                <TableCell>
                  <TaskDetailDialog
                    task={result}
                    trigger={
                      <Button variant="outline" size="sm">
                        View Details
                      </Button>
                    }
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {filteredResults.length === 0 && filter && (
        <div className="text-center py-4 text-muted-foreground">
          No tasks match your filters
        </div>
      )}
    </div>
  );
}
