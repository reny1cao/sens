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

  // Debug logging
  console.log('[QueryResults] Response structure:', {
    hasResponse: !!response,
    responseKeys: response ? Object.keys(response) : null,
    hasResults: !!response?.results,
    resultsKeys: response?.results ? Object.keys(response.results) : null,
    summaryInResults: (response?.results as any)?.summary,
    summaryInResponse: (response as any)?.summary,
    sql: response?.sql?.substring(0, 50) + '...',
    rowCount: response?.results?.row_count,
    columns: response?.results?.columns,
  });

  // Safety check for response
  if (!response || !response.results) {
    console.error('QueryResults: Invalid response', response);
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-4">
          <h3 className="text-red-800 font-medium mb-1">Error</h3>
          <p className="text-red-700">Invalid query response format</p>
        </CardContent>
      </Card>
    );
  }

  const { sql, results, metadata, summary } = response;
  const isSingleValue = results?.row_count === 1 && results?.columns?.length === 1;

  const exportCSV = () => {
    if (!results?.columns || !results?.data) {
      console.error('Cannot export CSV: Invalid results format');
      return;
    }

    const headers = results.columns.join(',');
    const rows = results.data.map(row =>
      results.columns.map(col => {
        const value = row?.[col];
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

      {/* Summary (if available) */}
      {summary && (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-6">
            <p className="text-blue-900">{summary}</p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Results</CardTitle>
              <CardDescription>
                {results?.row_count || 0} {results?.row_count === 1 ? 'row' : 'rows'} •
                {metadata?.execution_time_ms?.toFixed(0) || 0}ms
              </CardDescription>
            </div>
            {results?.row_count > 0 && (
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
          {!results || results.row_count === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No results found</p>
          ) : isSingleValue && results.data?.[0] && results.columns?.[0] ? (
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
