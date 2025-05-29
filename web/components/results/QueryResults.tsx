'use client';

import { useState } from 'react';
import { QueryResponse } from '@/types';
import { SQLDisplay } from './SQLDisplay';
import { ResultsTable } from './ResultsTable';
import { SingleValueCard } from './SingleValueCard';
import { Download, Table2, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface QueryResultsProps {
  response: QueryResponse;
}

export function QueryResults({ response }: QueryResultsProps) {
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table');

  const { sql, results, metadata } = response;
  const isSingleValue = results.row_count === 1 && results.columns.length === 1;

  const exportCSV = () => {
    const headers = results.columns.join(',');
    const rows = results.data.map(row =>
      results.columns.map(col => {
        const value = row[col];
        // Escape quotes and wrap in quotes if contains comma
        const stringValue = String(value ?? '');
        return stringValue.includes(',') || stringValue.includes('"')
          ? `"${stringValue.replace(/"/g, '""')}"`
          : stringValue;
      }).join(',')
    );
    const csv = [headers, ...rows].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `query_results_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* SQL Display */}
      <SQLDisplay sql={sql} />

      {/* Results */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Results</CardTitle>
              <CardDescription>
                {results.row_count} {results.row_count === 1 ? 'row' : 'rows'} •
                {metadata.execution_time_ms}ms
              </CardDescription>
            </div>
            {results.row_count > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={exportCSV}
              >
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {results.row_count === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No results found</p>
          ) : isSingleValue ? (
            <SingleValueCard
              value={results.data[0][results.columns[0]]}
              label={results.columns[0]}
            />
          ) : (
            <ResultsTable results={results} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
