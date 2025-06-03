import dagre from '@dagrejs/dagre';
import { Node, Edge } from 'reactflow';
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force';

export type LayoutType = 'hierarchical' | 'force' | 'grid';

interface SimulationNode extends Node {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export function layoutNodes(
  nodes: Node[], 
  edges: Edge[], 
  layoutType: LayoutType
): Node[] {
  switch (layoutType) {
    case 'hierarchical':
      return hierarchicalLayout(nodes, edges);
    case 'force':
      return forceLayout(nodes, edges);
    case 'grid':
      return gridLayout(nodes);
    default:
      return nodes;
  }
}

function hierarchicalLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ 
    rankdir: 'TB', 
    nodesep: 100, 
    ranksep: 150,
    marginx: 50,
    marginy: 50
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Add nodes to graph
  nodes.forEach((node) => {
    g.setNode(node.id, { 
      width: 350, 
      height: 200 
    });
  });

  // Add edges to graph
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  // Run layout
  dagre.layout(g);

  // Update node positions
  return nodes.map((node) => {
    const position = g.node(node.id);
    return {
      ...node,
      position: {
        x: position.x - 175, // Center the node (width/2)
        y: position.y - 100  // Center the node (height/2)
      }
    };
  });
}

function forceLayout(nodes: Node[], edges: Edge[]): Node[] {
  // Create simulation nodes
  const simNodes: SimulationNode[] = nodes.map(node => ({
    ...node,
    x: node.position.x || Math.random() * 1000,
    y: node.position.y || Math.random() * 1000
  }));

  // Create simulation links
  const simLinks = edges.map(edge => ({
    source: edge.source,
    target: edge.target
  }));

  // Create force simulation
  const simulation = forceSimulation(simNodes)
    .force('link', forceLink(simLinks)
      .id((d: any) => d.id)
      .distance(200)
      .strength(0.5)
    )
    .force('charge', forceManyBody()
      .strength(-1000)
      .distanceMax(500)
    )
    .force('center', forceCenter(500, 400))
    .force('collision', forceCollide(200))
    .alpha(1)
    .alphaDecay(0.02);

  // Run simulation
  simulation.tick(300);

  // Update positions
  return simNodes.map((simNode, index) => ({
    ...nodes[index],
    position: {
      x: simNode.x || 0,
      y: simNode.y || 0
    }
  }));
}

function gridLayout(nodes: Node[]): Node[] {
  const cols = Math.ceil(Math.sqrt(nodes.length));
  const spacing = 400;
  const startX = 100;
  const startY = 100;

  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: startX + (index % cols) * spacing,
      y: startY + Math.floor(index / cols) * spacing
    }
  }));
}