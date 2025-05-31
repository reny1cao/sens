'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Table, Database, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataPreview } from './DataPreview';
import { useDataSource } from '@/contexts/DataSourceContext';
import { cn } from '@/lib/utils';

export function DataSourceInfo() {
  const { activeSource, clearDataSource, deleteTable } = useDataSource();
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  if (!activeSource) {
    return null;
  }

  const toggleTable = (tableName: string) => {
    setExpandedTables(prev => {
      const next = new Set(prev);
      if (next.has(tableName)) {
        next.delete(tableName);
      } else {
        next.add(tableName);
      }
      return next;
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Data Schema
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearDataSource}
            title="Clear data source"
          >
            <X className="h-4 w-4" />
            Clear
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {activeSource.tables.map((table) => (
            <div key={table.name} className="border rounded-lg">
              <div
                className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50"
                onClick={() => toggleTable(table.name)}
              >
                <div className="flex items-center gap-2">
                  {expandedTables.has(table.name) ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <Table className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{table.name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {table.row_count.toLocaleString()} rows
                  </Badge>
                </div>
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <DataPreview table={table} />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteTable(table.name)}
                    className="h-8 w-8 p-0"
                    title={`Delete table ${table.name}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              
              {expandedTables.has(table.name) && (
                <div className="border-t px-3 py-2 bg-muted/20">
                  <div className="space-y-1">
                    {table.columns.map((column) => (
                      <div
                        key={column.name}
                        className="flex items-center justify-between py-1 px-2 text-sm"
                      >
                        <span className="font-mono">{column.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {column.type}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}