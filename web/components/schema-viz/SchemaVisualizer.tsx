'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  FolderTree, 
  GitBranch, 
  Network, 
  List,
  Search,
  Filter,
  Download,
  Maximize2
} from 'lucide-react';
import { 
  UniversalSchema, 
  SchemaVisualizationConfig 
} from '@/types/schema';
import { cn } from '@/lib/utils';

// Import visualization modes
import { ExplorerView } from './modes/ExplorerView';
import { GraphView } from './modes/GraphView';
import { ERDiagramView } from './modes/ERDiagramView';
import { CompactView } from './modes/CompactView';

// Import controls
import { SchemaSearch } from './controls/SchemaSearch';
import { FilterPanel } from './controls/FilterPanel';

interface SchemaVisualizerProps {
  schema: UniversalSchema;
  className?: string;
  defaultMode?: SchemaVisualizationConfig['mode'];
  onTableSelect?: (tableId: string) => void;
  onColumnSelect?: (tableId: string, columnId: string) => void;
}

export function SchemaVisualizer({
  schema,
  className,
  defaultMode = 'explorer',
  onTableSelect,
  onColumnSelect
}: SchemaVisualizerProps) {
  // Debug: Log schema on component mount/update
  useEffect(() => {
    console.log('SchemaVisualizer received schema:', schema);
    const dailyPrices = schema.entities.find(e => e.name === 'daily_prices');
    if (dailyPrices) {
      const tradeDateAttr = dailyPrices.attributes.find(a => a.name === 'trade_date');
      console.log('Trade date constraints in visualizer:', tradeDateAttr?.constraints);
    }
  }, [schema]);
  
  const [config, setConfig] = useState<SchemaVisualizationConfig>({
    mode: defaultMode,
    showStats: true,
    showDescriptions: true,
    groupByCategory: true,
    highlightRelationships: true
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Auto-switch to compact mode on mobile
  useEffect(() => {
    const checkScreenSize = () => {
      if (window.innerWidth < 768 && config.mode !== 'compact') {
        setConfig(prev => ({ ...prev, mode: 'compact' }));
      }
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);
    return () => window.removeEventListener('resize', checkScreenSize);
  }, [config.mode]);

  const viewModes = [
    { id: 'explorer', label: 'Explorer', icon: FolderTree },
    { id: 'graph', label: 'Graph', icon: Network },
    { id: 'er', label: 'ER Diagram', icon: GitBranch },
    { id: 'compact', label: 'List', icon: List }
  ] as const;

  const handleExport = () => {
    // Export schema as JSON or generate documentation
    const dataStr = JSON.stringify(schema, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `schema-${schema.source.name}-${new Date().toISOString()}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  return (
    <Card className={cn(
      "relative",
      isFullscreen && "fixed inset-0 z-50 rounded-none",
      className
    )}>
      {/* Header */}
      <div className="border-b p-3 sm:p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h3 className="text-base sm:text-lg font-semibold">Database Schema</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">
              {schema.source.name} ({schema.source.type}) - 
              {' '}{schema.metadata.totalTables} tables, 
              {' '}{schema.metadata.totalColumns} columns
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExport}
              title="Export schema"
              className="h-8 w-8 p-0 sm:h-9 sm:w-auto sm:px-3"
            >
              <Download className="h-4 w-4" />
              <span className="hidden sm:inline ml-2">Export</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsFullscreen(!isFullscreen)}
              title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              className="h-8 w-8 p-0"
            >
              <Maximize2 className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* View Mode Selector and Controls */}
        <div className="flex flex-col gap-3">
          {/* Mobile view mode selector - using native radio buttons */}
          <div className="md:hidden">
            <div className="flex gap-0 p-1 bg-muted rounded-lg" role="tablist">
              {viewModes.map((mode) => {
                const Icon = mode.icon;
                const isSelected = config.mode === mode.id;
                return (
                  <label
                    key={mode.id}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-md cursor-pointer transition-colors",
                      "text-sm font-medium",
                      isSelected 
                        ? "bg-background text-foreground shadow-sm" 
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <input
                      type="radio"
                      name="mobile-view-mode"
                      value={mode.id}
                      checked={isSelected}
                      onChange={() => setConfig(prev => ({ ...prev, mode: mode.id }))}
                      className="sr-only"
                      aria-label={`${mode.label} view`}
                    />
                    <Icon className="h-4 w-4" />
                    <span className="text-xs">{mode.label === 'ER Diagram' ? 'ER' : mode.label.slice(0, 5)}</span>
                  </label>
                );
              })}
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-4">
            {/* Desktop buttons */}
            <div className="hidden md:flex gap-1 p-1 bg-muted rounded-lg">
              {viewModes.map((mode) => {
                const Icon = mode.icon;
                return (
                  <Button
                    key={mode.id}
                    variant={config.mode === mode.id ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setConfig(prev => ({ ...prev, mode: mode.id }))}
                    className="gap-2"
                  >
                    <Icon className="h-4 w-4" />
                    <span className="hidden lg:inline">{mode.label}</span>
                  </Button>
                );
              })}
            </div>

            {/* Search and Filter */}
            <div className="flex items-center gap-2 flex-1">
              {/* Search */}
              <div className="flex-1 max-w-xs sm:max-w-sm">
                <SchemaSearch
                  schema={schema}
                  value={searchQuery}
                  onChange={setSearchQuery}
                  onSelect={(item) => {
                    if (item.type === 'table') {
                      onTableSelect?.(item.entity.id);
                    } else if (item.type === 'column' && item.attribute) {
                      onColumnSelect?.(item.entity.id, item.attribute.id);
                    }
                  }}
                />
              </div>

              {/* Filter */}
              <FilterPanel
                schema={schema}
                selectedCategories={selectedCategories}
                onCategoryChange={setSelectedCategories}
                config={config}
                onConfigChange={setConfig}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-3 sm:p-4 overflow-auto relative" style={{ height: isFullscreen ? 'calc(100vh - 180px)' : '600px' }}>
        {config.mode === 'explorer' && (
          <ExplorerView
            schema={schema}
            searchQuery={searchQuery}
            selectedCategories={selectedCategories}
            config={config}
            onTableSelect={onTableSelect}
            onColumnSelect={onColumnSelect}
          />
        )}
        
        {config.mode === 'graph' && (
          <GraphView
            schema={schema}
            searchQuery={searchQuery}
            selectedCategories={selectedCategories}
            config={config}
            onTableSelect={onTableSelect}
            onColumnSelect={onColumnSelect}
          />
        )}
        
        {config.mode === 'er' && (
          <ERDiagramView
            schema={schema}
            searchQuery={searchQuery}
            selectedCategories={selectedCategories}
            config={config}
            onTableSelect={onTableSelect}
            onColumnSelect={onColumnSelect}
          />
        )}
        
        {config.mode === 'compact' && (
          <CompactView
            schema={schema}
            searchQuery={searchQuery}
            selectedCategories={selectedCategories}
            config={config}
            onTableSelect={onTableSelect}
            onColumnSelect={onColumnSelect}
          />
        )}
      </div>
    </Card>
  );
}