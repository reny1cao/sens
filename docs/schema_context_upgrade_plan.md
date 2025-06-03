# Schema Context Upgrade Plan

## Overview
Leverage the enhanced schema model from visualization to upgrade schema context throughout the SENS pipeline, improving query understanding, retrieval, and SQL generation.

## Key Improvements

### 1. Enhanced Schema Context Model

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

class SemanticType(Enum):
    """Semantic meaning of data"""
    IDENTIFIER = "id"          # Primary/foreign keys
    TEMPORAL = "date"          # Dates, timestamps
    MONETARY = "money"         # Prices, costs
    QUANTITY = "quantity"      # Counts, volumes
    PERCENTAGE = "percentage"  # Rates, ratios
    TEXT = "text"             # Names, descriptions
    MEASURE = "measure"       # Other numeric measures

@dataclass
class EnhancedColumnContext:
    """Rich column context for better understanding"""
    name: str
    data_type: str
    semantic_type: SemanticType
    
    # New rich metadata
    display_name: str          # "Closing Price" vs "close_price"
    description: Optional[str] # "Daily closing price in USD"
    unit: Optional[str]        # "USD", "shares", "%"
    
    # Value insights
    examples: List[Any]        # Actual values from data
    value_range: Optional[tuple]  # (min, max) for numeric
    common_values: Optional[List[str]]  # For categorical
    
    # Relationships
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references: Optional[tuple] = None  # (table, column)
    
    # Statistics
    null_percentage: Optional[float] = None
    unique_count: Optional[int] = None
    
    # Query hints
    common_aggregations: List[str] = field(default_factory=list)  # ["AVG", "SUM"]
    filter_suggestions: List[str] = field(default_factory=list)    # ["> 100", "IN ('A','B')"]

@dataclass
class EnhancedTableContext:
    """Rich table context"""
    name: str
    display_name: str
    category: str              # "Market Data", "Reference"
    description: str
    
    # Structure
    columns: Dict[str, EnhancedColumnContext]
    primary_keys: List[str]
    
    # Insights
    row_count: int
    update_frequency: Optional[str]  # "daily", "real-time"
    common_joins: List[tuple]        # [(table, on_column)]
    
    # Partitioning info
    is_partitioned: bool = False
    partition_key: Optional[str] = None
    partition_strategy: Optional[str] = None  # "monthly", "yearly"

@dataclass
class EnhancedSchemaContext(BaseSchemaContext):
    """Upgraded schema context with rich metadata"""
    # Enhanced structure
    tables: Dict[str, EnhancedTableContext]
    
    # Semantic groupings
    categories: Dict[str, List[str]]  # category -> [table_names]
    
    # Value mappings
    value_mappings: Dict[str, Dict[str, str]]  # user_term -> db_value
    
    # Query patterns
    common_patterns: List[QueryPattern]
    
    # Global metadata
    source_type: str  # "postgresql", "mysql", "uploaded"
    last_analyzed: datetime
```

### 2. Improved Retrieval with Semantic Understanding

```python
@dataclass
class SemanticRetrievedColumn(RetrievedColumn):
    """Column with semantic understanding"""
    semantic_type: SemanticType
    semantic_score: float  # How well it matches intent
    
    # Why this column was selected
    selection_reasons: List[str]  # ["matches_date_filter", "likely_aggregate_target"]
    
    # Context for LLM
    usage_hint: Optional[str]  # "Use DATE_TRUNC for monthly aggregation"

class EnhancedRetriever:
    def retrieve_with_semantics(self, query: str) -> EnhancedRetrievedContext:
        # 1. Basic token/embedding search
        base_results = self.base_retriever.retrieve(query)
        
        # 2. Semantic enrichment
        if "average price" in query.lower():
            # Find monetary columns
            self._boost_semantic_type(results, SemanticType.MONETARY)
            # Add aggregation hints
            self._add_usage_hints(results, "AVG() for average calculations")
        
        if "last month" in query.lower():
            # Find temporal columns
            self._boost_semantic_type(results, SemanticType.TEMPORAL)
            # Add date filtering hints
            self._add_usage_hints(results, "DATE >= CURRENT_DATE - INTERVAL '1 month'")
        
        # 3. Category-based table selection
        if "financial" in query.lower():
            self._boost_category(results, "Financial Data")
        
        return EnhancedRetrievedContext(results)
```

### 3. Smarter SQL Generation

```python
class EnhancedSQLGenerator:
    def generate_with_context(self, 
                            question: str, 
                            context: EnhancedSchemaContext) -> str:
        # Use rich context for better SQL
        prompt = self._build_enhanced_prompt(question, context)
        
        # Include:
        # - Semantic types (know that close_price is money)
        # - Units (generate "AS price_usd")
        # - Common patterns (know to use DATE_TRUNC)
        # - Value mappings (map "Apple" to "AAPL")
        # - Partition hints (query right partitions)
        
        return self.llm.generate(prompt)
    
    def _build_enhanced_prompt(self, question: str, context: EnhancedSchemaContext):
        return f"""
        Generate SQL for: {question}
        
        Available Schema:
        {self._format_enhanced_schema(context)}
        
        Semantic Hints:
        - Monetary values are in {context.get_monetary_unit()}
        - Dates should use {context.get_date_format()}
        - Common aggregations: {context.get_common_aggregations()}
        
        Value Mappings:
        {context.get_relevant_mappings(question)}
        """
```

### 4. Integration Points

#### A. Schema Extraction Enhancement
```python
class EnhancedSchemaExtractor:
    def extract_with_analysis(self, connection) -> EnhancedSchemaContext:
        # 1. Basic structure
        base_schema = self.extract_structure(connection)
        
        # 2. Analyze data for semantics
        for table in base_schema.tables:
            for column in table.columns:
                # Detect semantic type
                column.semantic_type = self._infer_semantic_type(
                    column.name, 
                    column.data_type,
                    self._sample_values(table.name, column.name)
                )
                
                # Get statistics
                column.statistics = self._analyze_column(table.name, column.name)
                
                # Infer display name
                column.display_name = self._humanize_name(column.name)
        
        # 3. Detect relationships beyond FK
        base_schema.common_joins = self._analyze_query_logs()
        
        return base_schema
```

#### B. Retrieval System Upgrade
```python
# Before: Simple scoring
score = token_match_score + embedding_score

# After: Multi-dimensional scoring
score = (
    token_match_score * 0.3 +
    embedding_score * 0.3 +
    semantic_relevance_score * 0.2 +  # New!
    category_match_score * 0.1 +       # New!
    usage_frequency_score * 0.1        # New!
)
```

#### C. LLM Context Building
```python
# Before: Basic schema dump
"""
Tables: users, orders
Columns: users.id, users.name, orders.user_id, orders.total
"""

# After: Rich context
"""
## Customer Data (Reference)
Table: users (Customer Information)
- id: Customer identifier (examples: 1001, 1002)
- name: Customer full name

## Transactional Data (Orders)  
Table: orders (Purchase Orders) - Updates daily
- user_id: Links to users.id
- total: Order amount in USD (range: $10-$5000, avg: $127)

Common queries:
- Customer order history: JOIN users ON orders.user_id = users.id
- Revenue analysis: SUM(total) with DATE_TRUNC for time periods
"""
```

## Implementation Benefits

### 1. Better Query Understanding
- Map "Apple stock" → securities.symbol = 'AAPL'
- Understand "last quarter" → specific date range
- Recognize "revenue" → appropriate financial column

### 2. Improved Retrieval
- Select tables by semantic category
- Boost columns by semantic type
- Include related tables automatically

### 3. Smarter SQL Generation
- Generate appropriate aggregations
- Use correct date functions
- Apply proper type casting

### 4. Unified System
- Schema visualization = Schema context
- One source of truth
- Consistent understanding across UI and backend

## Migration Path

### Phase 1: Extend Current Models
```python
# Add optional enhanced fields to existing models
class LLMSchemaContext:
    # Existing fields...
    
    # New optional fields
    enhanced_metadata: Optional[Dict[str, EnhancedTableContext]] = None
    semantic_mappings: Optional[Dict[str, Any]] = None
```

### Phase 2: Parallel Implementation
- Build EnhancedSchemaContext alongside current
- A/B test with enhanced context
- Measure improvement metrics

### Phase 3: Full Migration
- Replace old context with enhanced
- Update all components
- Deprecate old models

## Success Metrics

1. **Query Success Rate**: 30% reduction in "no results" errors
2. **Retrieval Accuracy**: 25% improvement in relevant table selection  
3. **SQL Quality**: 40% reduction in type casting errors
4. **User Satisfaction**: Fewer clarification requests

## Conclusion

The schema visualization enhancements provide a perfect foundation for upgrading our schema context system. By sharing the same rich model between visualization and query processing, we create a more intelligent and user-friendly system.