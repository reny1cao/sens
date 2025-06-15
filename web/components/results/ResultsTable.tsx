'use client';

import { useState } from 'react';
import { QueryResults } from '@/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface ResultsTableProps {
  results: QueryResults;
}

export function ResultsTable({ results }: ResultsTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 10;

  // Safety checks
  if (!results || !results.columns || !results.data) {
    console.error('ResultsTable: Invalid results object', results);
    return (
      <div className="text-center py-8 text-muted-foreground">
        Error: Invalid results format
      </div>
    );
  }

  // Debug logging
  console.log('ResultsTable received:', {
    columns: results.columns,
    dataLength: results.data?.length || 0,
    firstRow: results.data?.[0],
    rowCount: results.row_count,
  });

  if (!Array.isArray(results.data) || results.data.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No data found
      </div>
    );
  }

  if (!Array.isArray(results.columns) || results.columns.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No columns defined
      </div>
    );
  }

  // Pagination calculations
  const totalPages = Math.ceil(results.data.length / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = Math.min(startIndex + rowsPerPage, results.data.length);
  const currentData = results.data.slice(startIndex, endIndex);

  const formatValue = (value: any, columnName?: string): React.ReactNode => {
    if (value === null || value === undefined) return <span className="text-muted-foreground">NULL</span>;

    // Format numbers with thousand separators
    if (typeof value === 'number') {
      if (columnName?.toLowerCase().includes('price') ||
          columnName?.toLowerCase().includes('amount') ||
          columnName?.toLowerCase().includes('volume')) {
        return (
          <span className="font-mono">
            {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        );
      }
      return <span className="font-mono">{value.toLocaleString()}</span>;
    }

    // Format dates
    if (columnName?.toLowerCase().includes('date') ||
        columnName?.toLowerCase().includes('time')) {
      try {
        const date = new Date(value);
        if (!isNaN(date.getTime())) {
          return (
            <span className="font-mono">
              {date.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
              })}
            </span>
          );
        }
      } catch {}
    }

    // Format booleans
    if (typeof value === 'boolean') {
      return (
        <Badge variant={value ? "default" : "secondary"}>
          {value ? 'True' : 'False'}
        </Badge>
      );
    }

    // Format objects/arrays
    if (typeof value === 'object') {
      return (
        <code className="text-xs bg-muted px-1 py-0.5 rounded">
          {JSON.stringify(value)}
        </code>
      );
    }

    // Default string formatting
    const strValue = String(value);
    if (strValue.length > 50) {
      return (
        <span title={strValue}>
          {strValue.substring(0, 50)}...
        </span>
      );
    }
    return strValue;
  };

  return (
    <div>
      <div className="rounded-md border">
        <div className="relative w-full overflow-auto max-h-[600px]">
          <Table>
            <TableHeader className="sticky top-0 bg-background z-10">
              <TableRow>
                <TableHead className="w-12 text-center">#</TableHead>
                {results.columns.map((column) => (
                  <TableHead key={column} className="font-medium whitespace-nowrap">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {currentData.map((row, idx) => (
                <TableRow key={startIndex + idx}>
                  <TableCell className="text-center text-muted-foreground font-mono text-sm">
                    {startIndex + idx + 1}
                  </TableCell>
                  {results.columns.map((column) => (
                    <TableCell key={column} className="max-w-[300px]">
                      {formatValue(row?.[column], column)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-muted-foreground">
            Showing {startIndex + 1} to {endIndex} of {results.data.length} rows
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <div className="text-sm">
              Page {currentPage} of {totalPages}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
