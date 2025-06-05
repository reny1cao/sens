// Types for enhanced schema visualization

export enum SemanticType {
  IDENTIFIER = 'id',
  TEMPORAL = 'date',
  MONETARY = 'money',
  QUANTITY = 'quantity',
  PERCENTAGE = 'percentage',
  TEXT = 'text',
  MEASURE = 'measure',
  BOOLEAN = 'boolean',
  JSON = 'json'
}

export interface SchemaAttribute {
  id: string;
  name: string;
  dataType: string;
  semanticType?: SemanticType;
  constraints: {
    primaryKey?: boolean;
    foreignKey?: { entity: string; attribute: string };
    unique?: boolean;
    nullable?: boolean;
    default?: any;
    partitionKey?: boolean;
  };
  metadata?: {
    description?: string;
    examples?: any[];
    statistics?: {
      min?: number;
      max?: number;
      uniqueCount?: number;
      nullPercentage?: number;
    };
    unit?: string;
  };
}

export interface EntityStats {
  rowCount: number;
  sizeBytes?: number;
  lastUpdated?: Date;
  updateFrequency?: string;
}

export interface SchemaEntity {
  id: string;
  name: string;
  type: 'table' | 'view' | 'collection' | 'type';
  category?: string;
  displayName?: string;
  description?: string;
  attributes: SchemaAttribute[];
  stats?: EntityStats;
  metadata?: Record<string, any>;
  // For partitioned tables
  isPartitioned?: boolean;
  partitionInfo?: {
    strategy: string;
    key: string;
    parentTable: string;
  };
}

export interface SchemaRelationship {
  id: string;
  source: string;
  target: string;
  type: 'one-to-one' | 'one-to-many' | 'many-to-many' | 'many-to-one';
  sourceAttribute: string;
  targetAttribute: string;
  label?: string;
}

export interface UniversalSchema {
  source: {
    type: 'postgresql' | 'mysql' | 'sqlite' | 'mongodb' | 'duckdb' | 'custom';
    version?: string;
    name: string;
  };
  entities: SchemaEntity[];
  relationships: SchemaRelationship[];
  categories?: Record<string, string[]>; // category -> entity ids
  metadata: {
    extractedAt: Date;
    totalTables: number;
    totalColumns: number;
    totalRelationships: number;
  };
}

export interface SchemaVisualizationConfig {
  mode: 'explorer' | 'graph' | 'er' | 'compact';
  showStats: boolean;
  showDescriptions: boolean;
  groupByCategory: boolean;
  highlightRelationships: boolean;
}

// Query pattern for smart suggestions
export interface QueryPattern {
  id: string;
  name: string;
  description: string;
  requiredTables: string[];
  commonFilters: Record<string, string>;
  exampleNL: string;
  sqlTemplate?: string;
  category: string;
}