'use client';

import { useState } from 'react';
import { ChevronRight, Table, Key, Link, Hash, Calendar, Type, DollarSign, Percent, ToggleLeft, FileJson, Database } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { UniversalSchema, SchemaEntity, SchemaVisualizationConfig, SemanticType } from '@/types/schema';
import { cn } from '@/lib/utils';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

interface CompactViewProps {
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

export function CompactView({
  schema,
  searchQuery,
  selectedCategories,
  config,
  onTableSelect,
  onColumnSelect
}: CompactViewProps) {
  const [expandedColumns, setExpandedColumns] = useState<Set<string>>(new Set());

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

  // Group entities by category if enabled
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

  const toggleColumns = (tableId: string) => {
    setExpandedColumns(prev => {
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
    const isExpanded = expandedColumns.has(entity.id);
    const primaryKeys = entity.attributes.filter(attr => attr.constraints.primaryKey);
    const foreignKeys = entity.attributes.filter(attr => attr.constraints.foreignKey);
    const keyColumns = [...primaryKeys, ...foreignKeys];

    return (
      <Card 
        key={entity.id} 
        className={cn(
          "mb-2",
          searchQuery && entity.name.toLowerCase().includes(searchQuery.toLowerCase()) && "ring-2 ring-yellow-400"
        )}
      >
        <div
          className="p-3"
          onClick={() => onTableSelect?.(entity.id)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Table className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <h4 className="font-medium text-sm break-all">
                  {entity.displayName || entity.name}
                </h4>
              </div>
              
              {config.showDescriptions && entity.description && (
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {entity.description}
                </p>
              )}
              
              <div className="flex flex-wrap items-center gap-2 mt-2 text-xs">
                {entity.category && (
                  <Badge variant="secondary" className="text-xs">
                    {entity.category}
                  </Badge>
                )}
                {entity.isPartitioned && (
                  <Badge variant="outline" className="text-xs">
                    Partitioned
                  </Badge>
                )}
                {config.showStats && entity.stats?.rowCount !== undefined && (
                  <span className="text-muted-foreground">
                    {entity.stats.rowCount.toLocaleString()} rows
                  </span>
                )}
                <span className="text-muted-foreground">
                  {entity.attributes.length} columns
                </span>
              </div>

              {/* Key columns preview */}
              {keyColumns.length > 0 && (
                <div className="mt-2 space-y-1">
                  {keyColumns.slice(0, 3).map(attr => (
                    <div key={attr.id} className="flex items-center gap-2 text-xs">
                      {attr.constraints.primaryKey ? (
                        <Badge variant="default" className="h-4 px-1">PK</Badge>
                      ) : (
                        <Badge variant="secondary" className="h-4 px-1">FK</Badge>
                      )}
                      <span className="font-mono">{attr.name}</span>
                    </div>
                  ))}
                  {keyColumns.length > 3 && (
                    <span className="text-xs text-muted-foreground">
                      +{keyColumns.length - 3} more keys
                    </span>
                  )}
                </div>
              )}
            </div>
            
            <Button
              variant="ghost"
              size="sm"
              className="flex-shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                toggleColumns(entity.id);
              }}
            >
              <ChevronRight className={cn(
                "h-4 w-4 transition-transform",
                isExpanded && "rotate-90"
              )} />
            </Button>
          </div>
        </div>
        
        {isExpanded && (
          <div className="border-t px-3 pb-3 pt-2 max-h-60 overflow-y-auto">
            <div className="space-y-1">
              {entity.attributes.map(attr => (
                <div
                  key={attr.id}
                  className={cn(
                    "flex items-center justify-between text-xs p-1 rounded hover:bg-muted/50 cursor-pointer",
                    searchQuery && attr.name.toLowerCase().includes(searchQuery.toLowerCase()) && "bg-yellow-100/50"
                  )}
                  onClick={() => onColumnSelect?.(entity.id, attr.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {getSemanticIcon(attr.semanticType)}
                    <span className="font-mono truncate">{attr.name}</span>
                    <div className="flex gap-1">
                      {attr.constraints.primaryKey && (
                        <Badge variant="outline" className="text-xs h-4 px-1">PK</Badge>
                      )}
                      {attr.constraints.foreignKey && (
                        <Badge variant="outline" className="text-xs h-4 px-1">FK</Badge>
                      )}
                    </div>
                  </div>
                  <span className="text-muted-foreground flex-shrink-0 ml-2">
                    {attr.dataType}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    );
  };

  // If grouped by category, use accordion
  if (config.groupByCategory && Object.keys(categorizedEntities).length > 0) {
    return (
      <div className="space-y-4">
        <Accordion type="multiple" className="space-y-2">
          {Object.entries(categorizedEntities).map(([category, entities]) => (
            <AccordionItem key={category} value={category} className="border rounded-lg">
              <AccordionTrigger className="px-4">
                <div className="flex items-center justify-between w-full pr-2">
                  <span className="font-medium">{category}</span>
                  <Badge variant="secondary">{entities.length}</Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-4">
                <div className="space-y-2">
                  {entities.map(renderEntity)}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
        
        {uncategorized.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Other Tables</h4>
            {uncategorized.map(renderEntity)}
          </div>
        )}
      </div>
    );
  }

  // Otherwise, simple list
  return (
    <div className="space-y-2">
      {filteredEntities.map(renderEntity)}
    </div>
  );
}