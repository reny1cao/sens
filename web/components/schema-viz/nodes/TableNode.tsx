'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Database, 
  Table, 
  Hash, 
  Calendar, 
  Type, 
  DollarSign,
  Percent,
  ToggleLeft,
  FileJson,
  Key,
  Link
} from 'lucide-react';
import { SchemaEntity, SemanticType } from '@/types/schema';
import { cn } from '@/lib/utils';

interface TableNodeData extends SchemaEntity {
  selected?: boolean;
  highlighted?: boolean;
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

function getCategoryColor(category?: string) {
  const colors: Record<string, string> = {
    'Market Data': 'bg-blue-500/10 text-blue-700 border-blue-500/20',
    'Reference Data': 'bg-green-500/10 text-green-700 border-green-500/20',
    'Analytics': 'bg-purple-500/10 text-purple-700 border-purple-500/20',
    'Financial': 'bg-amber-500/10 text-amber-700 border-amber-500/20',
    'System': 'bg-gray-500/10 text-gray-700 border-gray-500/20'
  };
  return colors[category || ''] || colors['System'];
}

export const TableNode = memo(({ data, selected }: NodeProps<TableNodeData>) => {
  const displayName = data.displayName || data.name;
  const primaryKeys = data.attributes.filter(attr => attr.constraints.primaryKey);
  const foreignKeys = data.attributes.filter(attr => attr.constraints.foreignKey);
  const maxVisibleColumns = 5;

  return (
    <>
      <Handle type="target" position={Position.Top} className="w-3 h-3" />
      
      <Card className={cn(
        "min-w-[200px] max-w-[280px] sm:min-w-[280px] sm:max-w-[350px] transition-all duration-200",
        selected && "ring-2 ring-primary",
        data.highlighted && "ring-2 ring-amber-500",
        "hover:shadow-lg cursor-pointer"
      )}>
        <CardHeader className="p-3 sm:pb-3 space-y-1 sm:space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1 sm:gap-2 min-w-0">
              <Table className="w-3 h-3 sm:w-4 sm:h-4 text-muted-foreground flex-shrink-0" />
              <span className="font-semibold text-xs sm:text-sm truncate">{displayName}</span>
            </div>
            {data.category && (
              <Badge 
                variant="outline" 
                className={cn("text-xs flex-shrink-0", getCategoryColor(data.category))}
              >
                {data.category}
              </Badge>
            )}
          </div>
          
          {data.description && (
            <p className="text-xs text-muted-foreground line-clamp-2 hidden sm:block">
              {data.description}
            </p>
          )}
          
          <div className="flex items-center gap-2 sm:gap-3 text-xs text-muted-foreground">
            {data.stats?.rowCount !== undefined && (
              <span className="hidden sm:inline">{data.stats.rowCount.toLocaleString()} rows</span>
            )}
            {data.isPartitioned && (
              <Badge variant="secondary" className="text-xs hidden sm:inline-flex">
                Partitioned
              </Badge>
            )}
            {primaryKeys.length > 0 && (
              <div className="flex items-center gap-0.5 sm:gap-1">
                <Key className="w-3 h-3" />
                <span>{primaryKeys.length}</span>
              </div>
            )}
            {foreignKeys.length > 0 && (
              <div className="flex items-center gap-0.5 sm:gap-1">
                <Link className="w-3 h-3" />
                <span>{foreignKeys.length}</span>
              </div>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="space-y-0.5 sm:space-y-1 p-2 sm:pb-3">
          {data.attributes.slice(0, maxVisibleColumns).map((attr) => (
            <div 
              key={attr.id} 
              className="flex items-center justify-between text-xs py-0.5 sm:py-1 px-1 sm:px-2 rounded hover:bg-muted/50"
            >
              <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
                {getSemanticIcon(attr.semanticType)}
                <span className="font-mono text-xs truncate">{attr.name}</span>
                {attr.constraints.primaryKey && (
                  <Badge variant="outline" className="ml-1 text-xs h-3 sm:h-4 px-0.5 sm:px-1 flex-shrink-0">PK</Badge>
                )}
                {attr.constraints.foreignKey && (
                  <Badge variant="outline" className="ml-1 text-xs h-3 sm:h-4 px-0.5 sm:px-1 flex-shrink-0">FK</Badge>
                )}
              </div>
              <span className="text-muted-foreground text-xs flex-shrink-0 ml-1">
                <span className="hidden sm:inline">{attr.dataType}</span>
                <span className="sm:hidden">{attr.dataType.split('(')[0]}</span>
                {attr.metadata?.unit && <span className="hidden lg:inline"> ({attr.metadata.unit})</span>}
              </span>
            </div>
          ))}
          
          {data.attributes.length > maxVisibleColumns && (
            <div className="text-xs text-muted-foreground pt-1 pl-2">
              +{data.attributes.length - maxVisibleColumns} more columns
            </div>
          )}
        </CardContent>
      </Card>
      
      <Handle type="source" position={Position.Bottom} className="w-3 h-3" />
    </>
  );
});

TableNode.displayName = 'TableNode';