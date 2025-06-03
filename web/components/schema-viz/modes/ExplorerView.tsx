'use client';

import { useState } from 'react';
import { ChevronRight, ChevronDown, Table, Eye, Database, Hash, Calendar, Type, DollarSign, Percent, ToggleLeft, FileJson, Key, Link } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { UniversalSchema, SchemaEntity, SchemaVisualizationConfig, SemanticType } from '@/types/schema';
import { cn } from '@/lib/utils';

interface ExplorerViewProps {
  schema: UniversalSchema;
  searchQuery: string;
  selectedCategories: string[];
  config: SchemaVisualizationConfig;
  onTableSelect?: (tableId: string) => void;
  onColumnSelect?: (tableId: string, columnId: string) => void;
}

function getSemanticIcon(type?: SemanticType) {
  switch (type) {
    case SemanticType.IDENTIFIER:
      return <Key className="w-3 h-3" />;
    case SemanticType.TEMPORAL:
      return <Calendar className="w-3 h-3" />;
    case SemanticType.MONETARY:
      return <DollarSign className="w-3 h-3" />;
    case SemanticType.QUANTITY:
      return <Hash className="w-3 h-3" />;
    case SemanticType.PERCENTAGE:
      return <Percent className="w-3 h-3" />;
    case SemanticType.TEXT:
      return <Type className="w-3 h-3" />;
    case SemanticType.BOOLEAN:
      return <ToggleLeft className="w-3 h-3" />;
    case SemanticType.JSON:
      return <FileJson className="w-3 h-3" />;
    default:
      return <Database className="w-3 h-3" />;
  }
}

export function ExplorerView({
  schema,
  searchQuery,
  selectedCategories,
  config,
  onTableSelect,
  onColumnSelect
}: ExplorerViewProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  // Filter entities based on search and categories
  const filteredEntities = schema.entities.filter(entity => {
    const matchesSearch = !searchQuery || 
      entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      entity.displayName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      entity.attributes.some(attr => 
        attr.name.toLowerCase().includes(searchQuery.toLowerCase())
      );
    
    const matchesCategory = selectedCategories.length === 0 ||
      (entity.category && selectedCategories.includes(entity.category));
    
    return matchesSearch && matchesCategory;
  });

  // Group entities by category
  const categorizedEntities: Record<string, SchemaEntity[]> = {};
  const uncategorized: SchemaEntity[] = [];

  filteredEntities.forEach(entity => {
    if (config.groupByCategory && entity.category) {
      if (!categorizedEntities[entity.category]) {
        categorizedEntities[entity.category] = [];
      }
      categorizedEntities[entity.category].push(entity);
    } else {
      uncategorized.push(entity);
    }
  });

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const toggleTable = (tableId: string) => {
    setExpandedTables(prev => {
      const next = new Set(prev);
      if (next.has(tableId)) {
        next.delete(tableId);
      } else {
        next.add(tableId);
      }
      return next;
    });
  };

  const renderEntity = (entity: SchemaEntity) => {
    const isExpanded = expandedTables.has(entity.id);
    const primaryKeys = entity.attributes.filter(attr => attr.constraints.primaryKey);
    const foreignKeys = entity.attributes.filter(attr => attr.constraints.foreignKey);

    return (
      <div key={entity.id} className="mb-2">
        <div
          className={cn(
            "flex items-center justify-between p-3 sm:p-2 rounded-lg hover:bg-muted/50 cursor-pointer touch-manipulation",
            searchQuery && entity.name.toLowerCase().includes(searchQuery.toLowerCase()) && "bg-yellow-100/50"
          )}
          onClick={() => {
            onTableSelect?.(entity.id);
            toggleTable(entity.id);
          }}
        >
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Button
              variant="ghost"
              size="sm"
              className="p-0 h-8 w-8 sm:h-5 sm:w-5 flex-shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                toggleTable(entity.id);
              }}
            >
              {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
            <Table className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <span className="font-medium text-sm truncate">{entity.displayName || entity.name}</span>
            {entity.isPartitioned && (
              <Badge variant="secondary" className="text-xs hidden sm:inline-flex">Partitioned</Badge>
            )}
          </div>
          
          <div className="flex items-center gap-2 text-xs text-muted-foreground flex-shrink-0">
            {config.showStats && entity.stats?.rowCount !== undefined && (
              <span className="hidden sm:inline">{entity.stats.rowCount.toLocaleString()} rows</span>
            )}
            {primaryKeys.length > 0 && (
              <div className="flex items-center gap-1">
                <Key className="w-3 h-3" />
                <span>{primaryKeys.length}</span>
              </div>
            )}
            {foreignKeys.length > 0 && (
              <div className="flex items-center gap-1">
                <Link className="w-3 h-3" />
                <span>{foreignKeys.length}</span>
              </div>
            )}
            <span className="hidden xs:inline">{entity.attributes.length} cols</span>
          </div>
        </div>

        {config.showDescriptions && entity.description && (
          <p className="text-xs text-muted-foreground ml-7 mt-1">
            {entity.description}
          </p>
        )}

        {isExpanded && (
          <div className="ml-4 sm:ml-7 mt-2 space-y-1">
            {entity.attributes.map(attr => (
              <div
                key={attr.id}
                className={cn(
                  "flex items-center justify-between text-xs p-2 sm:p-1.5 rounded hover:bg-muted/30 cursor-pointer touch-manipulation",
                  searchQuery && attr.name.toLowerCase().includes(searchQuery.toLowerCase()) && "bg-yellow-100/50"
                )}
                onClick={() => onColumnSelect?.(entity.id, attr.id)}
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {getSemanticIcon(attr.semanticType)}
                  <span className="font-mono truncate">{attr.name}</span>
                  <div className="flex gap-1 flex-shrink-0">
                    {attr.constraints.primaryKey && (
                      <Badge variant="outline" className="text-xs h-4 px-1">PK</Badge>
                    )}
                    {attr.constraints.foreignKey && (
                      <Badge variant="outline" className="text-xs h-4 px-1">FK</Badge>
                    )}
                    {attr.constraints.unique && (
                      <Badge variant="outline" className="text-xs h-4 px-1 hidden sm:inline-flex">UQ</Badge>
                    )}
                    {attr.constraints.partitionKey && (
                      <Badge variant="secondary" className="text-xs h-4 px-1">PARTITION</Badge>
                    )}
                  </div>
                </div>
                <span className="text-muted-foreground text-xs flex-shrink-0 ml-2">
                  <span className="hidden sm:inline">{attr.dataType}</span>
                  <span className="sm:hidden">{attr.dataType.split('(')[0]}</span>
                  {!attr.constraints.nullable && <span className="hidden lg:inline"> NOT NULL</span>}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Categorized entities */}
      {Object.entries(categorizedEntities).map(([category, entities]) => {
        const isExpanded = expandedCategories.has(category);
        return (
          <Card key={category} className="p-4">
            <div
              className="flex items-center justify-between mb-2 cursor-pointer"
              onClick={() => toggleCategory(category)}
            >
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="p-0 h-5 w-5"
                >
                  {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </Button>
                <h4 className="font-semibold">{category}</h4>
                <Badge variant="secondary">{entities.length}</Badge>
              </div>
              {config.showStats && (
                <span className="text-sm text-muted-foreground">
                  {entities.reduce((sum, e) => sum + (e.stats?.rowCount || 0), 0).toLocaleString()} total rows
                </span>
              )}
            </div>
            
            {isExpanded && (
              <div className="mt-2">
                {entities.map(renderEntity)}
              </div>
            )}
          </Card>
        );
      })}
      
      {/* Uncategorized entities */}
      {uncategorized.length > 0 && (
        <Card className="p-4">
          <h4 className="font-semibold mb-3">
            {config.groupByCategory ? 'Other Tables' : 'All Tables'}
            <Badge variant="secondary" className="ml-2">{uncategorized.length}</Badge>
          </h4>
          <div>
            {uncategorized.map(renderEntity)}
          </div>
        </Card>
      )}
    </div>
  );
}