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
import { 
  UniversalSchema, 
  SchemaEntity,
  SchemaVisualizationConfig 
} from '@/types/schema';
import { TableNode } from '../nodes/TableNode';
import { layoutNodes } from '../utils/layoutEngine';

interface GraphViewProps {
  schema: UniversalSchema;
  searchQuery: string;
  selectedCategories: string[];
  config: SchemaVisualizationConfig;
  onTableSelect?: (tableId: string) => void;
  onColumnSelect?: (tableId: string, columnId: string) => void;
}

const nodeTypes = {
  table: TableNode,
};

export function GraphView({
  schema,
  searchQuery,
  selectedCategories,
  config,
  onTableSelect,
  onColumnSelect
}: GraphViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [layout, setLayout] = useState<'hierarchical' | 'force' | 'grid'>('hierarchical');

  // Convert schema to React Flow nodes and edges
  useEffect(() => {
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

    // Create nodes
    const flowNodes: Node[] = filteredEntities.map(entity => ({
      id: entity.id,
      type: 'table',
      position: { x: 0, y: 0 }, // Will be set by layout
      data: entity
    }));

    // Create edges from relationships
    const flowEdges: Edge[] = schema.relationships
      .filter(rel => 
        filteredEntities.some(e => e.id === rel.source) &&
        filteredEntities.some(e => e.id === rel.target)
      )
      .map(rel => ({
        id: rel.id,
        source: rel.source,
        target: rel.target,
        type: 'smoothstep',
        animated: config.highlightRelationships,
        label: rel.label,
        labelStyle: { fontSize: 12 },
        style: { 
          stroke: '#64748b',
          strokeWidth: 2
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 20,
          height: 20,
        },
      }));

    // Apply layout
    const layoutedNodes = layoutNodes(flowNodes, flowEdges, layout);
    
    setNodes(layoutedNodes);
    setEdges(flowEdges);
  }, [schema, searchQuery, selectedCategories, config, layout]);

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
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
      >
        <Background variant="dots" gap={12} size={1} />
        
        <MiniMap 
          nodeColor={nodeColor}
          nodeStrokeWidth={3}
          pannable
          zoomable
          style={{
            backgroundColor: 'hsl(var(--background))',
            border: '1px solid hsl(var(--border))',
          }}
        />
        
        <Controls />
        
        <Panel position="top-right" className="flex gap-2">
          <Card className="p-2">
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={layout === 'hierarchical' ? 'default' : 'outline'}
                onClick={() => setLayout('hierarchical')}
              >
                Tree
              </Button>
              <Button
                size="sm"
                variant={layout === 'force' ? 'default' : 'outline'}
                onClick={() => setLayout('force')}
              >
                Force
              </Button>
              <Button
                size="sm"
                variant={layout === 'grid' ? 'default' : 'outline'}
                onClick={() => setLayout('grid')}
              >
                Grid
              </Button>
            </div>
          </Card>
        </Panel>
      </ReactFlow>
    </div>
  );
}