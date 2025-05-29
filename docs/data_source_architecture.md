# Data Source Architecture

## Overview

SENS needs to handle multiple data sources intelligently for mixed users who may not know where their data lives.

## Data Source Selection Strategies

### 1. **Automatic Context Detection**

```python
class DataSourceResolver:
    """Intelligently resolve which data sources to query."""

    def __init__(self):
        self.data_sources = {
            'sales_db': {
                'domains': ['revenue', 'sales', 'orders', 'customers'],
                'tables': ['orders', 'customers', 'products', 'transactions'],
                'weight': 1.0
            },
            'analytics_db': {
                'domains': ['metrics', 'kpi', 'performance', 'trends'],
                'tables': ['daily_metrics', 'user_analytics', 'funnel_data'],
                'weight': 0.8
            },
            'support_db': {
                'domains': ['tickets', 'support', 'issues', 'satisfaction'],
                'tables': ['tickets', 'feedback', 'nps_scores'],
                'weight': 0.7
            },
            'marketing_db': {
                'domains': ['campaigns', 'marketing', 'acquisition', 'channels'],
                'tables': ['campaigns', 'utm_data', 'attribution'],
                'weight': 0.6
            }
        }

    async def resolve_sources(self, query: str, intent: Intent) -> List[DataSource]:
        """Determine relevant data sources based on query intent."""

        # 1. Extract domain keywords
        keywords = self.extract_keywords(query)

        # 2. Score each data source
        scores = {}
        for source_name, config in self.data_sources.items():
            score = 0.0

            # Domain matching
            for keyword in keywords:
                if keyword in config['domains']:
                    score += 1.0 * config['weight']

            # Intent matching
            if intent.entities:
                for entity in intent.entities:
                    if entity.lower() in config['domains']:
                        score += 0.5 * config['weight']

            scores[source_name] = score

        # 3. Return relevant sources (score > threshold)
        relevant_sources = [
            source for source, score in scores.items()
            if score > 0.3
        ]

        return sorted(relevant_sources, key=lambda x: scores[x], reverse=True)
```

### 2. **User-Guided Selection**

```typescript
// Progressive disclosure for data source selection

interface DataSourceSelection {
    automatic: DataSource[];      // What we think you need
    suggested: DataSource[];      // Might also be useful
    available: DataSource[];      // Everything else
}

// UI Flow
function selectDataSources(query: string): DataSourceSelection {
    const selection = resolveDataSources(query);

    // For beginners: Use automatic selection
    if (userLevel === 'beginner') {
        return {
            automatic: selection.automatic,
            suggested: [],
            available: []
        };
    }

    // For analysts: Show suggestions
    if (userLevel === 'analyst') {
        return {
            automatic: selection.automatic,
            suggested: selection.suggested,
            available: selection.available
        };
    }

    // For developers: Show everything
    return selection;
}
```

### 3. **Smart Defaults with Override**

```yaml
# User preferences configuration
user_preferences:
  default_sources:
    - sales_db         # Always check sales first
    - analytics_db     # Then analytics

  domain_mappings:
    "customer": [sales_db, support_db]
    "revenue": [sales_db, finance_db]
    "marketing": [marketing_db, analytics_db]

  exclusions:
    - test_db         # Never query test databases
    - archive_db      # Exclude archived data
```

### 4. **Context-Aware Data Catalog**

```python
class DataCatalog:
    """Maintains metadata about all available data sources."""

    def __init__(self):
        self.catalog = {
            'sales_db.orders': {
                'description': 'Customer orders and transactions',
                'update_frequency': 'real-time',
                'common_queries': ['revenue', 'sales', 'orders'],
                'relationships': ['customers', 'products'],
                'data_quality': 0.95,
                'query_cost': 'low'
            },
            'analytics_db.daily_metrics': {
                'description': 'Pre-aggregated daily business metrics',
                'update_frequency': 'daily',
                'common_queries': ['kpi', 'trends', 'performance'],
                'relationships': ['dimensions'],
                'data_quality': 0.99,
                'query_cost': 'very_low'
            }
        }

    def suggest_sources(self, intent: str) -> List[DataSourceInfo]:
        """Suggest data sources based on query intent."""
        suggestions = []

        for source, metadata in self.catalog.items():
            relevance_score = self.calculate_relevance(intent, metadata)
            if relevance_score > 0.5:
                suggestions.append(DataSourceInfo(
                    source=source,
                    relevance=relevance_score,
                    description=metadata['description'],
                    query_cost=metadata['query_cost']
                ))

        return sorted(suggestions, key=lambda x: x.relevance, reverse=True)
```

## Implementation Approach

### Phase 1: Single Database (Current)
- Keep current implementation
- Focus on single database queries
- Perfect the schema understanding

### Phase 2: Multi-Database Support
1. **Add data source configuration**
   ```python
   # settings.py
   DATA_SOURCES = {
       'primary': os.getenv('SENS_DB_URL'),
       'analytics': os.getenv('SENS_ANALYTICS_DB_URL'),
       'support': os.getenv('SENS_SUPPORT_DB_URL')
   }
   ```

2. **Extend schema extraction**
   ```bash
   sens extract-schema --source primary -o primary_schema.json
   sens extract-schema --source analytics -o analytics_schema.json
   sens build-index --schemas primary_schema.json,analytics_schema.json
   ```

3. **Update retrieval logic**
   - Tag each table with its source database
   - Include source in context
   - Generate queries with proper database prefixes

### Phase 3: Intelligent Routing
1. **Intent-based routing**
   - Map intents to likely data sources
   - Learn from user corrections
   - Build domain knowledge

2. **User preferences**
   - Remember user's data source choices
   - Build personal routing rules
   - Suggest based on history

3. **Cost optimization**
   - Route to pre-aggregated data when possible
   - Warn about expensive cross-database joins
   - Suggest alternatives

## UI/UX Patterns

### For Beginners
```
Q: "Show me customer satisfaction"

🤖 I'll check our customer feedback data for you...
   ✓ Found satisfaction scores in Customer Support database

   [Show results]
```

### For Analysts
```
Q: "Show me customer satisfaction"

🤖 I found relevant data in multiple places:

   📊 Customer Support DB (Recommended)
      └─ NPS scores, feedback surveys

   📊 Sales DB (Additional context)
      └─ Customer lifetime value, churn rates

   Include data from: [✓ Support] [✓ Sales] [Run Query]
```

### For Developers
```
Q: "Show me customer satisfaction"

🤖 Data source resolution:

   Primary: support_db.nps_scores (score: 0.95)
   Secondary: sales_db.customer_metrics (score: 0.72)

   Generated query will use:
   - support_db.nps_scores
   - support_db.feedback
   - LEFT JOIN sales_db.customers

   [Edit sources] [View SQL] [Run Query]
```

## Best Practices

1. **Start Simple**
   - Single database first
   - Add sources gradually
   - Learn from usage patterns

2. **Be Transparent**
   - Show which data is being queried
   - Explain why sources were chosen
   - Allow overrides

3. **Optimize for Common Cases**
   - 80% of queries hit primary database
   - Pre-configure common patterns
   - Cache source mappings

4. **Handle Edge Cases**
   - Cross-database joins
   - Missing permissions
   - Stale data warnings
