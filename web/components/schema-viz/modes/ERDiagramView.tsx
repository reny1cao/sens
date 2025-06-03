'use client';

import { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  ConnectionMode,
  Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Toggle } from '@/components/ui/toggle';
import { Eye, EyeOff } from 'lucide-react';
import { 
  UniversalSchema, 
  SchemaEntity,
  SchemaVisualizationConfig,
  SchemaAttribute 
} from '@/types/schema';
import { cn } from '@/lib/utils';
import { layoutNodes } from '../utils/layoutEngine';

interface ERDiagramViewProps {
  schema: UniversalSchema;
  searchQuery: string;
  selectedCategories: string[];
  config: SchemaVisualizationConfig;
  onTableSelect?: (tableId: string) => void;
  onColumnSelect?: (tableId: string, columnId: string) => void;
}

interface ERNodeData extends SchemaEntity {
  selected?: boolean;
  highlighted?: boolean;
  showColumns?: boolean;
}

// Custom node component for ER diagram
const ERNode = ({ data, selected }: { data: ERNodeData; selected?: boolean }) => {
  const primaryKeys = data.attributes.filter(attr => attr.constraints.primaryKey);
  const foreignKeys = data.attributes.filter(attr => attr.constraints.foreignKey && !attr.constraints.primaryKey);
  const partitionKeys = data.attributes.filter(attr => attr.constraints.partitionKey && !attr.constraints.primaryKey);
  const regularColumns = data.attributes.filter(
    attr => !attr.constraints.primaryKey && !attr.constraints.foreignKey && !attr.constraints.partitionKey
  );

  return (
    <Card className={cn(
      "min-w-[200px] sm:min-w-[250px] transition-all duration-200",
      selected && "ring-2 ring-primary",
      data.highlighted && "ring-2 ring-amber-500"
    )}>
      <div className="p-2 sm:p-3 border-b bg-muted/30">
        <h4 className="font-semibold text-xs sm:text-sm truncate">{data.displayName || data.name}</h4>
      </div>
      
      {data.showColumns !== false && (
        <div className="p-1.5 sm:p-2 space-y-1.5 sm:space-y-2">
          {/* Primary Keys */}
          {primaryKeys.length > 0 && (
            <div className="space-y-0.5 sm:space-y-1">
              {primaryKeys.map(attr => (
                <div key={attr.id} className="flex items-center gap-1 sm:gap-2 text-xs">
                  <span className="font-bold text-primary text-xs">PK</span>
                  {attr.constraints.partitionKey && (
                    <span className="font-bold text-green-600 text-xs">+PART</span>
                  )}
                  <span className="font-mono truncate flex-1">{attr.name}</span>
                  <span className="text-muted-foreground text-xs hidden sm:inline">{attr.dataType}</span>
                </div>
              ))}
            </div>
          )}
          
          {/* Foreign Keys */}
          {foreignKeys.length > 0 && (
            <div className="space-y-0.5 sm:space-y-1 border-t pt-1.5 sm:pt-2">
              {foreignKeys.map(attr => (
                <div key={attr.id} className="flex items-center gap-1 sm:gap-2 text-xs">
                  <span className="font-bold text-blue-600 text-xs">FK</span>
                  <span className="font-mono truncate flex-1">{attr.name}</span>
                  <span className="text-muted-foreground text-xs hidden sm:inline">{attr.dataType}</span>
                </div>
              ))}
            </div>
          )}
          
          {/* Partition Keys */}
          {partitionKeys.length > 0 && (
            <div className="space-y-0.5 sm:space-y-1 border-t pt-1.5 sm:pt-2">
              {partitionKeys.map(attr => (
                <div key={attr.id} className="flex items-center gap-1 sm:gap-2 text-xs">
                  <span className="font-bold text-green-600 text-xs">PT</span>
                  <span className="font-mono truncate flex-1">{attr.name}</span>
                  <span className="text-muted-foreground text-xs hidden sm:inline">{attr.dataType}</span>
                </div>
              ))}
            </div>
          )}
          
          {/* Regular Columns (limited) */}
          {regularColumns.length > 0 && data.showColumns && (
            <div className="space-y-0.5 sm:space-y-1 border-t pt-1.5 sm:pt-2">
              {regularColumns.slice(0, 3).map(attr => (
                <div key={attr.id} className="flex items-center gap-1 sm:gap-2 text-xs">
                  <span className="w-4 sm:w-6"></span>
                  <span className="font-mono truncate flex-1">{attr.name}</span>
                  <span className="text-muted-foreground text-xs hidden lg:inline">{attr.dataType}</span>
                </div>
              ))}
              {regularColumns.length > 3 && (
                <div className="text-xs text-muted-foreground pl-4 sm:pl-6">
                  +{regularColumns.length - 3} more...
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

const nodeTypes = {
  er: ERNode,
};

export function ERDiagramView({
  schema,
  searchQuery,
  selectedCategories,
  config,
  onTableSelect,
  onColumnSelect
}: ERDiagramViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [showAllColumns, setShowAllColumns] = useState(false);
  const [layout, setLayout] = useState<'hierarchical' | 'force'>('hierarchical');

  // Convert schema to ER diagram nodes and edges
  useEffect(() => {
    // Filter entities based on search and categories
    const filteredEntities = schema.entities.filter(entity => {
      const matchesSearch = !searchQuery || 
        entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entity.displayName?.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesCategory = selectedCategories.length === 0 ||
        (entity.category && selectedCategories.includes(entity.category));
      
      return matchesSearch && matchesCategory;
    });

    // Create nodes
    const flowNodes: Node[] = filteredEntities.map(entity => ({
      id: entity.id,
      type: 'er',
      position: { x: 0, y: 0 },
      data: {
        ...entity,
        showColumns: showAllColumns
      } as ERNodeData
    }));

    // Create edges from foreign key relationships
    const flowEdges: Edge[] = [];
    const edgeSet = new Set<string>();

    filteredEntities.forEach(entity => {
      entity.attributes.forEach(attr => {
        if (attr.constraints.foreignKey) {
          const targetEntity = filteredEntities.find(
            e => e.id === attr.constraints.foreignKey?.entity
          );
          
          if (targetEntity) {
            const edgeId = `${entity.id}-${targetEntity.id}-${attr.id}`;
            if (!edgeSet.has(edgeId)) {
              edgeSet.add(edgeId);
              flowEdges.push({
                id: edgeId,
                source: entity.id,
                target: targetEntity.id,
                type: 'smoothstep',
                animated: config.highlightRelationships,
                label: attr.name,
                labelStyle: { fontSize: 10 },
                style: { 
                  stroke: '#3b82f6',
                  strokeWidth: 2
                },
                markerEnd: {
                  type: MarkerType.Arrow,
                  width: 15,
                  height: 15,
                },
              });
            }
          }
        }
      });
    });

    // Apply layout
    const layoutedNodes = layoutNodes(flowNodes, flowEdges, layout);
    
    setNodes(layoutedNodes);
    setEdges(flowEdges);
  }, [schema, searchQuery, selectedCategories, config, showAllColumns, layout]);

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    onTableSelect?.(node.id);
  }, [onTableSelect]);

  const nodeColor = useCallback((node: Node) => {
    const entity = node.data as SchemaEntity;
    const categoryColors: Record<string, string> = {
      'Market Data': '#3b82f6',
      'Reference Data': '#10b981',
      'Analytics': '#8b5cf6',
      'Financial': '#f59e0b',
      'System': '#6b7280'
    };
    return categoryColors[entity.category || ''] || '#6b7280';
  }, []);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.1, maxZoom: 1 }}
        attributionPosition="bottom-left"
        zoomOnScroll={true}
        zoomOnPinch={true}
        panOnScroll={false}
        panOnDrag={true}
        preventScrolling={true}
        nodesDraggable={true}
        nodesConnectable={false}
        minZoom={0.1}
        maxZoom={2}
      >
        <Background variant={'dots' as any} gap={12} size={1} />
        
        <MiniMap 
          nodeColor={nodeColor}
          nodeStrokeWidth={3}
          pannable
          zoomable
          className="hidden lg:block"
          style={{
            backgroundColor: 'hsl(var(--background))',
            border: '1px solid hsl(var(--border))',
          }}
        />
        
        <Controls className="left-2 bottom-2 md:left-auto md:bottom-auto" />
        
        <Panel position="top-right" className="flex gap-2">
          <Card className="p-1 sm:p-2">
            <div className="flex items-center gap-1 sm:gap-2">
              <Toggle
                pressed={showAllColumns}
                onPressedChange={setShowAllColumns}
                size="sm"
                aria-label="Toggle column visibility"
                className="text-xs sm:text-sm"
              >
                {showAllColumns ? <Eye className="h-3 w-3 sm:h-4 sm:w-4" /> : <EyeOff className="h-3 w-3 sm:h-4 sm:w-4" />}
                <span className="ml-1 hidden sm:inline">Columns</span>
              </Toggle>
              
              <div className="w-px h-6 bg-border hidden sm:block" />
              
              <Button
                size="sm"
                variant={layout === 'hierarchical' ? 'default' : 'outline'}
                onClick={() => setLayout('hierarchical')}
                className="text-xs sm:text-sm px-2 sm:px-3"
              >
                <span className="hidden sm:inline">Tree</span>
                <span className="sm:hidden">T</span>
              </Button>
              <Button
                size="sm"
                variant={layout === 'force' ? 'default' : 'outline'}
                onClick={() => setLayout('force')}
                className="text-xs sm:text-sm px-2 sm:px-3"
              >
                <span className="hidden sm:inline">Force</span>
                <span className="sm:hidden">F</span>
              </Button>
            </div>
          </Card>
        </Panel>
      </ReactFlow>
    </div>
  );
}