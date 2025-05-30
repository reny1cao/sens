'use client';

import { QueryResults } from '@/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface ResultsTableProps {
  results: QueryResults;
}

export function ResultsTable({ results }: ResultsTableProps) {
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

  const formatCellValue = (value: any): string => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'boolean') return value ? 'True' : 'False';
    if (typeof value === 'number') {
      // Format large numbers with commas
      if (Number.isInteger(value) && Math.abs(value) > 999) {
        return value.toLocaleString();
      }
      // Format decimals to 2 places
      if (!Number.isInteger(value)) {
        return value.toFixed(2);
      }
      return value.toString();
    }
    if (value instanceof Date) {
      return value.toLocaleDateString();
    }
    // Handle long strings
    const str = String(value);
    if (str.length > 100) {
      return str.substring(0, 100) + '...';
    }
    return str;
  };

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

  return (
    <div className="rounded-md border">
      <div className="relative w-full overflow-auto max-h-[600px]">
        <Table>
          <TableHeader className="sticky top-0 bg-background z-10">
            <TableRow>
              {results.columns.map((column) => (
                <TableHead key={column} className="font-medium whitespace-nowrap">
                  {column}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.data.map((row, rowIndex) => (
              <TableRow key={rowIndex}>
                {results.columns.map((column) => (
                  <TableCell
                    key={column}
                    className="max-w-[300px] truncate"
                    title={String(row?.[column] || '')}
                  >
                    {formatCellValue(row?.[column])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
