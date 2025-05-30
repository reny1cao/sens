'use client';

import { useState } from 'react';
import { Database, Upload, Link, ChevronDown, Table, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { FileUpload } from './FileUpload';
import { useDataSource } from '@/contexts/DataSourceContext';
import { DataSourceType } from '@/types';

export function DataSourceSelector() {
  const { activeSource, clearDataSource, deleteTable } = useDataSource();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedMode, setSelectedMode] = useState<'upload' | 'connect' | null>(null);

  const getSourceIcon = (type: DataSourceType) => {
    switch (type) {
      case 'uploaded_file':
        return <Upload className="h-4 w-4" />;
      case 'connected_db':
        return <Link className="h-4 w-4" />;
      default:
        return <Database className="h-4 w-4" />;
    }
  };

  const getSourceBadgeVariant = (type: DataSourceType) => {
    switch (type) {
      case 'uploaded_file':
        return 'secondary';
      case 'connected_db':
        return 'outline';
      default:
        return 'default';
    }
  };

  return (
    <>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              {activeSource ? (
                <>
                  {getSourceIcon(activeSource.type)}
                  <span className="max-w-[200px] truncate">{activeSource.name}</span>
                  <Badge variant={getSourceBadgeVariant(activeSource.type)} className="ml-2">
                    {activeSource.tables.length} tables
                  </Badge>
                </>
              ) : (
                <>
                  <Database className="h-4 w-4" />
                  <span>Default Database</span>
                </>
              )}
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[300px]">
            <DropdownMenuLabel>Data Source</DropdownMenuLabel>
            <DropdownMenuSeparator />
            
            {activeSource && (
              <>
                <div className="px-2 py-1.5 text-sm text-muted-foreground">
                  Current source:
                </div>
                <div className="px-2 pb-2 space-y-2">
                  <div className="flex items-center justify-between p-2 bg-muted rounded-md">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      {getSourceIcon(activeSource.type)}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{activeSource.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {activeSource.tables.length} {activeSource.tables.length === 1 ? 'table' : 'tables'} • {activeSource.totalRows.toLocaleString()} rows
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={clearDataSource}
                      className="h-6 w-6 p-0 flex-shrink-0 ml-2"
                      title="Clear all data"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  
                  {/* Show individual tables */}
                  {activeSource.tables.map((table) => (
                    <div key={table.name} className="pl-6 pr-2">
                      <div className="flex items-center justify-between text-sm group hover:bg-muted/50 rounded p-1">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <Table className="h-3 w-3 text-muted-foreground" />
                          <span className="font-mono text-xs truncate">{table.name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            {table.row_count.toLocaleString()} rows
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteTable(table.name);
                            }}
                            className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                            title={`Delete table ${table.name}`}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <DropdownMenuSeparator />
              </>
            )}
            
            <DialogTrigger asChild>
              <DropdownMenuItem
                onSelect={() => {
                  setSelectedMode('upload');
                  setDialogOpen(true);
                }}
              >
                <Upload className="mr-2 h-4 w-4" />
                Upload Files
              </DropdownMenuItem>
            </DialogTrigger>
            
            <DropdownMenuItem disabled>
              <Link className="mr-2 h-4 w-4" />
              Connect Database
              <Badge variant="outline" className="ml-auto text-xs">
                Coming Soon
              </Badge>
            </DropdownMenuItem>
            
            {activeSource && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <Table className="mr-2 h-4 w-4" />
                  View Schema
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {selectedMode === 'upload' ? 'Upload Data Files' : 'Connect to Database'}
            </DialogTitle>
            <DialogDescription>
              {selectedMode === 'upload'
                ? 'Upload CSV or Excel files to query your own data'
                : 'Connect to an external database'}
            </DialogDescription>
          </DialogHeader>

          {selectedMode === 'upload' && (
            <FileUpload />
          )}

          {selectedMode === 'connect' && (
            <div className="text-center py-8 text-muted-foreground">
              Database connection feature coming soon...
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}