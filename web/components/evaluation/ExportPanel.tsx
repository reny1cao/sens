/**
 * Export Panel Component
 *
 * Provides export functionality for BIRD-CRITIC evaluation results
 * in various formats including official submission format.
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle, Download, FileText, Code, BarChart3, Send } from 'lucide-react';

interface ExportPanelProps {
  onExport: (format: 'submission' | 'detailed' | 'sql_only' | 'metrics') => Promise<void>;
  isCompleted: boolean;
  evaluationId?: string;
  metrics: Record<string, any>;
}

interface ExportOption {
  format: 'submission' | 'detailed' | 'sql_only' | 'metrics';
  title: string;
  description: string;
  icon: React.ReactNode;
  fileExtension: string;
  isOfficialFormat?: boolean;
}

export function ExportPanel({ onExport, isCompleted, evaluationId, metrics }: ExportPanelProps) {
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);

  const exportOptions: ExportOption[] = [
    {
      format: 'submission',
      title: 'BIRD-CRITIC Submission',
      description: 'Official JSONL format for BIRD-CRITIC submission with instance_id, predicted_sql, and prompt_flow',
      icon: <Send className="h-4 w-4" />,
      fileExtension: 'jsonl',
      isOfficialFormat: true,
    },
    {
      format: 'detailed',
      title: 'Detailed Results',
      description: 'Complete evaluation results with all task details, errors, and execution information',
      icon: <FileText className="h-4 w-4" />,
      fileExtension: 'json',
    },
    {
      format: 'sql_only',
      title: 'SQL Only',
      description: 'Just the generated SQL queries mapped by task ID for quick reference',
      icon: <Code className="h-4 w-4" />,
      fileExtension: 'json',
    },
    {
      format: 'metrics',
      title: 'Metrics Summary',
      description: 'Comprehensive metrics including success rates, timing, and error analysis',
      icon: <BarChart3 className="h-4 w-4" />,
      fileExtension: 'json',
    },
  ];

  const handleExport = async (format: ExportOption['format']) => {
    setExportingFormat(format);
    try {
      await onExport(format);
    } catch (error) {
      console.error('Export failed:', error);
      // You might want to show a toast notification here
    } finally {
      setExportingFormat(null);
    }
  };

  const submissionMetrics = metrics.submission_ready || {};

  return (
    <div className="space-y-6">
      {/* Status Alert */}
      {!isCompleted ? (
        <Alert>
          <AlertDescription>
            Export options will be available once the evaluation is completed.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>
            Evaluation completed successfully! You can now export results in various formats.
          </AlertDescription>
        </Alert>
      )}

      {/* BIRD-CRITIC Submission Info */}
      {isCompleted && (
        <Card className="border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-700 dark:text-green-300">
              <Send className="h-5 w-5" />
              BIRD-CRITIC Submission Ready
            </CardTitle>
            <CardDescription>
              Your evaluation results are ready for official BIRD-CRITIC submission
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {submissionMetrics.execution_accuracy?.toFixed(3) || '0.000'}
                </div>
                <div className="text-sm text-muted-foreground">Execution Accuracy</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {submissionMetrics.sql_generation_coverage?.toFixed(3) || '0.000'}
                </div>
                <div className="text-sm text-muted-foreground">SQL Coverage</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {submissionMetrics.performance_ms?.toFixed(1) || '0.0'}ms
                </div>
                <div className="text-sm text-muted-foreground">Avg Performance</div>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-900 p-4 rounded border">
              <h4 className="font-medium text-sm mb-2">Submission Instructions</h4>
              <div className="text-sm space-y-1 text-muted-foreground">
                <p><strong>Email Title:</strong> [BIRD-CRITIC-1.0-postgresql][SENS Team][Agent-Based NL2SQL]</p>
                <p><strong>Email To:</strong> bird.bench25@gmail.com</p>
                <p><strong>Attach:</strong> Download the "BIRD-CRITIC Submission" file below</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Export Options */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {exportOptions.map((option) => (
          <Card
            key={option.format}
            className={option.isOfficialFormat ? 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950' : ''}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                {option.icon}
                {option.title}
                {option.isOfficialFormat && (
                  <Badge variant="default" className="text-xs">Official</Badge>
                )}
              </CardTitle>
              <CardDescription className="text-xs">
                {option.description}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                  Format: .{option.fileExtension}
                </div>
                <Button
                  onClick={() => handleExport(option.format)}
                  disabled={!isCompleted || exportingFormat === option.format}
                  size="sm"
                  variant={option.isOfficialFormat ? 'default' : 'outline'}
                >
                  {exportingFormat === option.format ? (
                    <>
                      <div className="animate-spin mr-2 h-3 w-3 border border-current border-t-transparent rounded-full" />
                      Exporting...
                    </>
                  ) : (
                    <>
                      <Download className="h-3 w-3 mr-2" />
                      Download
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* File Information */}
      {isCompleted && evaluationId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Export Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span>Evaluation ID:</span>
              <code className="bg-muted px-1 py-0.5 rounded text-xs">{evaluationId}</code>
            </div>
            <div className="flex justify-between">
              <span>Export Date:</span>
              <span>{new Date().toLocaleString()}</span>
            </div>
            {metrics.total_tasks && (
              <div className="flex justify-between">
                <span>Total Tasks:</span>
                <span>{metrics.total_tasks}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Help Text */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Export Formats Guide</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>
            <strong>BIRD-CRITIC Submission:</strong> Use this file for official benchmark submission.
            Contains the required JSONL format with instance_id, predicted_sql array, and prompt_flow.
          </div>
          <div>
            <strong>Detailed Results:</strong> Complete evaluation data including queries, SQL,
            execution results, errors, and timing information for analysis.
          </div>
          <div>
            <strong>SQL Only:</strong> Quick reference file mapping task IDs to generated SQL queries.
            Useful for code review or manual testing.
          </div>
          <div>
            <strong>Metrics Summary:</strong> Comprehensive performance metrics including success rates,
            execution times, error breakdowns, and submission-ready statistics.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
