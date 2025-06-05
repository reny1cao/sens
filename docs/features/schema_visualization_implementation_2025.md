# Schema Visualization Implementation Plan 2025

## Executive Summary
Implement a flexible, modern schema visualization system using React Flow and D3.js, styled with shadcn UI components, that works with any database schema (not just our financial data).

## Technology Stack Analysis

### Current Setup
- **UI Framework**: Next.js 15.3.2 with React 19
- **Component Library**: shadcn UI (Tailwind-based)
- **State Management**: Zustand
- **Data Fetching**: React Query v5
- **Icons**: Lucide React
- **Charts**: Recharts (already installed)

### Recommended Libraries for Schema Visualization

#### Primary Choice: React Flow
```bash
pnpm add reactflow
```
**Why React Flow?**
- Built for React with TypeScript support
- Highly customizable nodes and edges
- Great performance with large graphs
- Active community and maintenance
- Works seamlessly with Tailwind CSS

#### Supporting Libraries
```bash
pnpm add @dagrejs/dagre  # For auto-layout
pnpm add d3-force d3-hierarchy  # For force-directed layouts
pnpm add @react-spring/web  # For smooth animations
```

## Implementation Architecture

### 1. Core Components Structure

```typescript
// Base schema visualization components
components/
  schema-viz/
    SchemaVisualizer.tsx         // Main container
    modes/
      ExplorerView.tsx          // Tree/list view
      GraphView.tsx             // React Flow network
      ERDiagramView.tsx         // ER relationships
      CompactView.tsx           // Minimal view
    nodes/
      TableNode.tsx             // Custom table node
      ColumnNode.tsx            // Column details
      RelationshipEdge.tsx      // Custom edge
    controls/
      ViewToggle.tsx            // Switch between views
      SearchBar.tsx             // Schema search
      FilterPanel.tsx           // Filter by type/category
      ZoomControls.tsx          // Navigation
    utils/
      layoutEngine.ts           // Auto-layout algorithms
      schemaParser.ts           // Parse any schema format
      colorScheme.ts            // Consistent theming
```

### 2. Universal Schema Model

```typescript
// Works with any database, not tied to financial data
interface UniversalSchema {
  source: {
    type: 'postgresql' | 'mysql' | 'sqlite' | 'mongodb' | 'duckdb' | 'custom';
    version?: string;
    name: string;
  };
  
  entities: SchemaEntity[];
  relationships: SchemaRelationship[];
  metadata: SchemaMetadata;
}

interface SchemaEntity {
  id: string;
  name: string;
  type: 'table' | 'view' | 'collection' | 'type';
  category?: string;  // User-defined grouping
  attributes: SchemaAttribute[];
  stats?: EntityStats;
  metadata?: Record<string, any>;
}

interface SchemaAttribute {
  id: string;
  name: string;
  dataType: string;
  semanticType?: 'id' | 'date' | 'numeric' | 'text' | 'boolean' | 'json';
  constraints: {
    primaryKey?: boolean;
    foreignKey?: { entity: string; attribute: string };
    unique?: boolean;
    nullable?: boolean;
    default?: any;
  };
  metadata?: {
    description?: string;
    examples?: any[];
    statistics?: Record<string, any>;
  };
}
```

### 3. React Flow Custom Nodes

```tsx
// TableNode.tsx - Styled with shadcn UI
import { Handle, Position } from 'reactflow';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Database, Table, Hash, Calendar, Type } from 'lucide-react';

export function TableNode({ data }: { data: SchemaEntity }) {
  const getIcon = (type: string) => {
    switch (type) {
      case 'id': return <Hash className="w-3 h-3" />;
      case 'date': return <Calendar className="w-3 h-3" />;
      case 'text': return <Type className="w-3 h-3" />;
      default: return <Database className="w-3 h-3" />;
    }
  };

  return (
    <Card className="min-w-[250px] shadow-lg">
      <Handle type="target" position={Position.Top} />
      
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Table className="w-4 h-4" />
            <span className="font-semibold">{data.name}</span>
          </div>
          <Badge variant="secondary" className="text-xs">
            {data.stats?.rowCount || 0} rows
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-1">
        {data.attributes.slice(0, 5).map((attr) => (
          <div key={attr.id} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-1">
              {getIcon(attr.semanticType || '')}
              <span className="font-mono">{attr.name}</span>
              {attr.constraints.primaryKey && <Badge variant="outline" className="ml-1 text-xs">PK</Badge>}
            </div>
            <span className="text-muted-foreground text-xs">{attr.dataType}</span>
          </div>
        ))}
        {data.attributes.length > 5 && (
          <div className="text-xs text-muted-foreground pt-1">
            +{data.attributes.length - 5} more columns
          </div>
        )}
      </CardContent>
      
      <Handle type="source" position={Position.Bottom} />
    </Card>
  );
}
```

### 4. Layout Strategies

```typescript
// layoutEngine.ts
import dagre from '@dagrejs/dagre';
import { Node, Edge } from 'reactflow';

export const layoutStrategies = {
  // Hierarchical layout for ER diagrams
  hierarchical: (nodes: Node[], edges: Edge[]) => {
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: 'TB', nodesep: 100, ranksep: 100 });
    g.setDefaultEdgeLabel(() => ({}));
    
    nodes.forEach((node) => {
      g.setNode(node.id, { width: 250, height: 150 });
    });
    
    edges.forEach((edge) => {
      g.setEdge(edge.source, edge.target);
    });
    
    dagre.layout(g);
    
    return nodes.map((node) => {
      const position = g.node(node.id);
      return { ...node, position: { x: position.x, y: position.y } };
    });
  },
  
  // Force-directed for complex relationships
  force: async (nodes: Node[], edges: Edge[]) => {
    // D3 force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(400, 300));
    
    // Run simulation
    await simulation.tick(300);
    return nodes;
  },
  
  // Grid layout for many tables
  grid: (nodes: Node[]) => {
    const cols = Math.ceil(Math.sqrt(nodes.length));
    return nodes.map((node, i) => ({
      ...node,
      position: {
        x: (i % cols) * 300,
        y: Math.floor(i / cols) * 200
      }
    }));
  }
};
```

### 5. Smart Features

```tsx
// Schema Search with Fuzzy Matching
import { Command } from '@/components/ui/command';

export function SchemaSearch({ schema, onSelect }) {
  const searchableItems = [
    ...schema.entities.map(e => ({ 
      type: 'table', 
      name: e.name, 
      label: `Table: ${e.name}`,
      entity: e 
    })),
    ...schema.entities.flatMap(e => 
      e.attributes.map(a => ({
        type: 'column',
        name: `${e.name}.${a.name}`,
        label: `${e.name}.${a.name} (${a.dataType})`,
        entity: e,
        attribute: a
      }))
    )
  ];
  
  return (
    <Command className="rounded-lg border shadow-md">
      <CommandInput placeholder="Search tables, columns..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Tables">
          {searchableItems
            .filter(item => item.type === 'table')
            .map(item => (
              <CommandItem key={item.name} onSelect={() => onSelect(item)}>
                <Table className="mr-2 h-4 w-4" />
                {item.label}
              </CommandItem>
            ))}
        </CommandGroup>
        <CommandGroup heading="Columns">
          {searchableItems
            .filter(item => item.type === 'column')
            .map(item => (
              <CommandItem key={item.name} onSelect={() => onSelect(item)}>
                <Hash className="mr-2 h-4 w-4" />
                {item.label}
              </CommandItem>
            ))}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}
```

### 6. Interactive Features

```tsx
// Minimap and Controls
import { ReactFlow, MiniMap, Controls, Background } from 'reactflow';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export function GraphView({ schema }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [layout, setLayout] = useState('hierarchical');
  
  const nodeTypes = {
    table: TableNode,
    view: ViewNode,
  };
  
  return (
    <div className="h-[600px] w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background variant="dots" gap={12} size={1} />
        <MiniMap 
          nodeColor={(node) => {
            switch (node.data.category) {
              case 'dimension': return '#10b981';
              case 'fact': return '#3b82f6';
              case 'staging': return '#f59e0b';
              default: return '#6b7280';
            }
          }}
          style={{
            backgroundColor: 'hsl(var(--background))',
            border: '1px solid hsl(var(--border))',
          }}
        />
        <Controls />
        
        {/* Custom Controls Panel */}
        <Card className="absolute top-4 right-4 p-2">
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={layout === 'hierarchical' ? 'default' : 'outline'}
              onClick={() => applyLayout('hierarchical')}
            >
              Tree
            </Button>
            <Button
              size="sm"
              variant={layout === 'force' ? 'default' : 'outline'}
              onClick={() => applyLayout('force')}
            >
              Force
            </Button>
            <Button
              size="sm"
              variant={layout === 'grid' ? 'default' : 'outline'}
              onClick={() => applyLayout('grid')}
            >
              Grid
            </Button>
          </div>
        </Card>
      </ReactFlow>
    </div>
  );
}
```

### 7. Responsive Design

```tsx
// Adaptive view based on screen size
export function SchemaVisualizer({ schema }) {
  const [view, setView] = useState<'explorer' | 'graph' | 'er' | 'compact'>('explorer');
  const { width } = useWindowSize();
  
  // Auto-switch to compact on mobile
  useEffect(() => {
    if (width < 768) {
      setView('compact');
    }
  }, [width]);
  
  return (
    <div className="space-y-4">
      {/* View Toggle - Hidden on mobile */}
      <div className="hidden md:flex gap-2">
        <Button
          variant={view === 'explorer' ? 'default' : 'outline'}
          onClick={() => setView('explorer')}
        >
          <FolderTree className="w-4 h-4 mr-2" />
          Explorer
        </Button>
        {/* ... other view buttons */}
      </div>
      
      {/* Render appropriate view */}
      <AnimatePresence mode="wait">
        {view === 'explorer' && <ExplorerView schema={schema} />}
        {view === 'graph' && <GraphView schema={schema} />}
        {view === 'er' && <ERDiagramView schema={schema} />}
        {view === 'compact' && <CompactView schema={schema} />}
      </AnimatePresence>
    </div>
  );
}
```

## Performance Optimizations

### 1. Virtualization for Large Schemas
```tsx
import { Virtuoso } from 'react-virtuoso';

// For schemas with 100+ tables
export function VirtualizedTableList({ tables }) {
  return (
    <Virtuoso
      style={{ height: '600px' }}
      data={tables}
      itemContent={(index, table) => (
        <TableCard key={table.id} table={table} />
      )}
    />
  );
}
```

### 2. Progressive Loading
```tsx
// Load schema details on demand
const { data: schemaOverview } = useQuery({
  queryKey: ['schema', 'overview'],
  queryFn: fetchSchemaOverview,
});

const { data: tableDetails } = useQuery({
  queryKey: ['schema', 'table', selectedTable],
  queryFn: () => fetchTableDetails(selectedTable),
  enabled: !!selectedTable,
});
```

## Deliverables

### Phase 1: Core Visualization (Week 1)
- [ ] Install React Flow and dependencies
- [ ] Create base components
- [ ] Implement Explorer view
- [ ] Basic search functionality

### Phase 2: Graph Visualization (Week 2)
- [ ] React Flow integration
- [ ] Custom nodes and edges
- [ ] Auto-layout algorithms
- [ ] Minimap and controls

### Phase 3: Interactive Features (Week 3)
- [ ] Advanced search with fuzzy matching
- [ ] Relationship navigation
- [ ] Export functionality
- [ ] Performance optimizations

### Phase 4: Polish & Integration (Week 4)
- [ ] Animations and transitions
- [ ] Dark mode support
- [ ] Mobile optimizations
- [ ] Documentation

This implementation provides a modern, performant schema visualization system that works with any database, not just our financial data, while maintaining consistency with our shadcn UI design system.