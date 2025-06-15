// API Types for SENS Web Interface

export interface QueryRequest {
  question: string;
  context?: QueryContext;
}

export interface QueryContext {
  conversation_id?: string;
  previous_queries?: string[];
  user_preferences?: UserPreferences;
}

export interface UserPreferences {
  default_limit?: number;
  preferred_format?: 'table' | 'chart' | 'summary';
  show_sql?: boolean;
}

export interface QueryResponse {
  sql: string;
  results: QueryResults;
  metadata: QueryMetadata;
  summary?: string;  // Natural language summary of the results
  error?: ErrorDetail;
}

export interface QueryResults {
  columns: string[];
  data: Record<string, any>[];
  row_count: number;
  truncated?: boolean;
}

export interface QueryMetadata {
  execution_time_ms: number;
  confidence_score?: number;
  tables_used: string[];
  query_type: 'select' | 'aggregate' | 'complex';
  suggested_visualizations?: VisualizationType[];
  pipeline_metrics?: PipelineMetrics;
}

export interface PipelineMetrics {
  steps: PipelineStep[];
  total_duration?: number;
}

export interface PipelineStep {
  name: string;
  status: 'started' | 'success' | 'failed';
  start_time?: string;
  end_time?: string;
  duration?: number;
  error?: string;
  metadata?: Record<string, any>;
}

export type VisualizationType =
  | 'table'
  | 'bar_chart'
  | 'line_chart'
  | 'pie_chart'
  | 'single_value'
  | 'time_series';

export interface ErrorDetail {
  code: string;
  message: string;
  suggestion?: string;
  technical_details?: string;
}

// Query Processing Steps
export interface ProcessingStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  message?: string;
  details?: string;
  startTime?: number;
  endTime?: number;
}

export const PROCESSING_STEPS: ProcessingStep[] = [
  { id: 'understanding', name: 'Understanding your request', status: 'pending' },
  { id: 'finding_data', name: 'Finding relevant data', status: 'pending' },
  { id: 'generating_sql', name: 'Generating SQL query', status: 'pending' },
  { id: 'validating', name: 'Validating query', status: 'pending' },
  { id: 'executing', name: 'Executing query', status: 'pending' },
];

// Schema Types
export interface SchemaTable {
  name: string;
  description?: string;
  columns: SchemaColumn[];
  row_count?: number;
  relationships?: TableRelationship[];
}

export interface SchemaColumn {
  name: string;
  type: string;
  description?: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  referenced_table?: string;
  referenced_column?: string;
  is_sticky?: boolean;
}

export interface TableRelationship {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  relationship_type: 'one_to_one' | 'one_to_many' | 'many_to_many';
}

// Query History
export interface QueryHistoryItem {
  id: string;
  question: string;
  sql: string;
  timestamp: string;
  execution_time_ms: number;
  row_count: number;
  is_favorite?: boolean;
  tags?: string[];
}

// UI State
export interface UIState {
  mode: 'beginner' | 'analyst' | 'developer';
  theme: 'light' | 'dark' | 'system';
  showSQL: boolean;
  autoExecute: boolean;
  queryHistory: QueryHistoryItem[];
  savedQueries: SavedQuery[];
}

export interface SavedQuery {
  id: string;
  name: string;
  description?: string;
  question: string;
  sql: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

// Data Source Types
export type DataSourceType = 'default_postgres' | 'uploaded_file' | 'connected_db';

export interface DataSource {
  id: string;
  name: string;
  type: DataSourceType;
  tables: TableInfo[];
  totalRows: number;
  createdAt: Date;
}

export interface TableInfo {
  name: string;
  columns: ColumnInfo[];
  row_count: number;
  sample_data?: Record<string, any>[];
}

export interface ColumnInfo {
  name: string;
  type: string;
}

export interface DataSourceResponse {
  session_id: string;
  source_id: string;
  type: DataSourceType;
  name: string;
  tables: TableInfo[];
  total_rows: number;
  message?: string;
}

export interface TablePreview {
  table_name: string;
  columns: string[];
  row_count: number;
  data: Record<string, any>[];
}
