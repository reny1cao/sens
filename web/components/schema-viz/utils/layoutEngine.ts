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
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const nodeWidth = isMobile ? 250 : 350;
  const nodeHeight = isMobile ? 150 : 200;
  
  const g = new dagre.graphlib.Graph();
  g.setGraph({ 
    rankdir: 'TB', 
    nodesep: isMobile ? 50 : 100, 
    ranksep: isMobile ? 100 : 150,
    marginx: isMobile ? 20 : 50,
    marginy: isMobile ? 20 : 50
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Add nodes to graph
  nodes.forEach((node) => {
    g.setNode(node.id, { 
      width: nodeWidth, 
      height: nodeHeight 
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
        x: position.x - nodeWidth / 2, // Center the node
        y: position.y - nodeHeight / 2  // Center the node
      }
    };
  });
}

function forceLayout(nodes: Node[], edges: Edge[]): Node[] {
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const centerX = isMobile ? 200 : 500;
  const centerY = isMobile ? 300 : 400;
  const nodeDistance = isMobile ? 150 : 200;
  const collisionRadius = isMobile ? 150 : 200;
  
  // Create simulation nodes
  const simNodes: SimulationNode[] = nodes.map(node => ({
    ...node,
    x: node.position.x || Math.random() * (isMobile ? 400 : 1000),
    y: node.position.y || Math.random() * (isMobile ? 600 : 1000)
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
      .distance(nodeDistance)
      .strength(0.5)
    )
    .force('charge', forceManyBody()
      .strength(isMobile ? -500 : -1000)
      .distanceMax(isMobile ? 300 : 500)
    )
    .force('center', forceCenter(centerX, centerY))
    .force('collision', forceCollide(collisionRadius))
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
  // Adjust columns based on screen width (assuming mobile if we have many nodes)
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const cols = isMobile ? Math.min(2, Math.ceil(Math.sqrt(nodes.length))) : Math.ceil(Math.sqrt(nodes.length));
  const spacing = isMobile ? 250 : 400;
  const startX = isMobile ? 50 : 100;
  const startY = isMobile ? 50 : 100;

  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: startX + (index % cols) * spacing,
      y: startY + Math.floor(index / cols) * spacing
    }
  }));
}