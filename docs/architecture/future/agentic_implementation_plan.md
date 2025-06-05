# Agentic Query System Implementation Plan

## Quick Start Guide

This document provides a practical implementation plan for the agentic query architecture, breaking it down into manageable tasks.

## Phase 1: Foundation (Week 1)

### Task 1.1: Value Discovery Infrastructure
```python
# src/sens/discovery/__init__.py
# src/sens/discovery/value_searcher.py

class ValueSearcher:
    """Search for values across database columns."""
    
    async def search_distinct_values(
        self,
        table: str,
        column: str,
        pattern: str = None,
        limit: int = 100
    ) -> List[str]:
        """Get distinct values from a column with optional pattern matching."""
        # Implementation: Execute SQL to get distinct values
        # Cache results for performance
        
    async def fuzzy_search_values(
        self,
        search_term: str,
        table: str,
        column: str,
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """Find values similar to search term using trigram similarity."""
        # Use PostgreSQL's pg_trgm extension
        # SELECT value, similarity(value, search_term) as score
        # WHERE similarity(value, search_term) > threshold
```

### Task 1.2: Value Mapping Store
```python
# src/sens/discovery/value_mapper.py

class ValueMappingStore:
    """Store and retrieve mappings between user terms and database values."""
    
    def __init__(self):
        # Static mappings for common terms
        self.static_mappings = {
            "tech": ["Technology", "Information Technology"],
            "finance": ["Financial Services", "Financials", "Banking"],
            "apple": ["AAPL", "Apple Inc."],
            "google": ["GOOGL", "Alphabet Inc."],
        }
        
        # Dynamic mappings learned from queries
        self.learned_mappings = {}
        
    async def get_mapping(self, user_term: str) -> List[str]:
        """Get all known mappings for a user term."""
        
    async def add_mapping(
        self, 
        user_term: str, 
        db_value: str, 
        confidence: float,
        context: Dict[str, Any]
    ):
        """Add a new learned mapping."""
```

## Phase 2: Query Planning Agent (Week 2)

### Task 2.1: ReAct Framework
```python
# src/sens/agent/react.py

class ReActAgent:
    """ReAct (Reasoning + Acting) agent for query planning."""
    
    def __init__(self, tools: Dict[str, Tool]):
        self.tools = tools
        self.max_steps = 10
        
    async def plan(self, query: str) -> QueryPlan:
        """Create a query plan using ReAct loop."""
        thoughts = []
        observations = []
        
        for step in range(self.max_steps):
            # Generate thought
            thought = await self.think(query, thoughts, observations)
            thoughts.append(thought)
            
            # Decide action
            action = await self.decide_action(thought)
            
            # Execute action
            observation = await self.execute_action(action)
            observations.append(observation)
            
            # Check if plan is complete
            if self.is_plan_complete(thoughts, observations):
                break
                
        return self.compile_plan(thoughts, observations)
```

### Task 2.2: Agent Tools
```python
# src/sens/agent/tools.py

class AgentTools:
    """Tools available to the query planning agent."""
    
    @tool
    async def search_table_values(
        self, 
        table: str, 
        column: str, 
        pattern: str
    ) -> List[str]:
        """Search for values in a specific table column."""
        
    @tool
    async def get_column_statistics(
        self,
        table: str,
        column: str
    ) -> Dict[str, Any]:
        """Get statistics about a column (min, max, count, distinct)."""
        
    @tool
    async def find_similar_terms(
        self,
        term: str,
        context: str
    ) -> List[str]:
        """Find database terms similar to user input."""
        
    @tool
    async def resolve_temporal_reference(
        self,
        temporal_ref: str,
        base_date: datetime = None
    ) -> Tuple[datetime, datetime]:
        """Convert relative time references to date ranges."""
```

## Phase 3: Self-Correcting Executor (Week 3)

### Task 3.1: Query Diagnostic System
```python
# src/sens/execution/diagnostics.py

class QueryDiagnostics:
    """Diagnose why queries return empty results."""
    
    async def diagnose_empty_result(
        self,
        sql: str,
        context: QueryContext
    ) -> Diagnosis:
        """Analyze why a query returned no results."""
        
        # Check each condition in WHERE clause
        conditions = self.extract_conditions(sql)
        for condition in conditions:
            if await self.is_value_mismatch(condition):
                return Diagnosis(
                    type="value_mismatch",
                    details={"condition": condition},
                    suggestion="Try alternative values"
                )
                
        # Check date ranges
        if self.has_date_filter(sql):
            if await self.is_date_range_too_narrow(sql):
                return Diagnosis(
                    type="date_range_issue",
                    details={"current_range": self.extract_date_range(sql)},
                    suggestion="Expand date range"
                )
```

### Task 3.2: Query Correction Strategies
```python
# src/sens/execution/corrections.py

class QueryCorrector:
    """Apply corrections to queries based on diagnostics."""
    
    async def correct_value_mismatch(
        self,
        sql: str,
        diagnosis: Diagnosis
    ) -> str:
        """Fix value mismatches in WHERE conditions."""
        # Extract the problematic value
        problem_value = diagnosis.details["value"]
        
        # Find alternative values
        alternatives = await self.value_mapper.find_alternatives(problem_value)
        
        # Try each alternative
        for alt in alternatives:
            corrected_sql = self.replace_value(sql, problem_value, alt)
            if await self.test_query(corrected_sql):
                return corrected_sql
                
        return sql  # No correction found
```

## Phase 4: Learning System (Week 4)

### Task 4.1: Query History Tracking
```python
# src/sens/learning/history.py

class QueryHistoryTracker:
    """Track query execution history for learning."""
    
    async def record_execution(
        self,
        user_query: str,
        generated_sql: str,
        result: QueryResult,
        corrections: List[Correction],
        final_mappings: Dict[str, str]
    ):
        """Record a complete query execution."""
        
        execution_record = {
            "timestamp": datetime.now(),
            "user_query": user_query,
            "generated_sql": generated_sql,
            "success": result.row_count > 0,
            "corrections_applied": corrections,
            "value_mappings": final_mappings,
            "execution_time_ms": result.execution_time
        }
        
        await self.store.save(execution_record)
```

### Task 4.2: Pattern Learning
```python
# src/sens/learning/patterns.py

class PatternLearner:
    """Learn patterns from successful queries."""
    
    async def learn_from_success(
        self,
        execution: ExecutionRecord
    ):
        """Extract and store patterns from successful queries."""
        
        # Learn value mappings
        for user_term, db_value in execution.value_mappings.items():
            await self.value_mapper.strengthen_mapping(
                user_term, 
                db_value,
                confidence_boost=0.1
            )
            
        # Learn query patterns
        pattern = self.extract_pattern(execution.user_query)
        await self.pattern_store.add_successful_pattern(
            pattern,
            execution.generated_sql
        )
```

## Integration Plan

### Week 5: Integration with ChatOrchestrator

```python
# src/sens/chat/enhanced_orchestrator.py

class EnhancedChatOrchestrator(ChatOrchestrator):
    """ChatOrchestrator with agentic capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize new components
        self.value_searcher = ValueSearcher()
        self.value_mapper = ValueMappingStore()
        self.agent = ReActAgent(self._create_tools())
        self.diagnostics = QueryDiagnostics()
        self.corrector = QueryCorrector()
        self.history_tracker = QueryHistoryTracker()
        self.pattern_learner = PatternLearner()
        
    async def step(
        self,
        state: ConversationState,
        user_input: str
    ) -> Tuple[Response, ConversationState]:
        """Enhanced step with agentic reasoning."""
        
        # 1. Use agent to create query plan
        plan = await self.agent.plan(user_input)
        
        # 2. Update schema context with discovered values
        enhanced_context = await self._enhance_context_with_values(
            self.retrieval_context,
            plan.discovered_mappings
        )
        
        # 3. Generate SQL with enhanced context
        sql = await self.sql_generator.generate(
            user_input,
            enhanced_context,
            value_mappings=plan.discovered_mappings
        )
        
        # 4. Execute with self-correction
        result = await self._execute_with_correction(sql, plan)
        
        # 5. Learn from execution
        await self._learn_from_execution(
            user_input, sql, result, plan
        )
        
        return result, state
```

## Testing Strategy

### Unit Tests
- Value searcher with mock database
- Mapping store persistence
- Agent reasoning steps
- Diagnostic accuracy
- Correction strategies

### Integration Tests
- End-to-end query with value discovery
- Self-correction scenarios
- Learning system updates
- Performance benchmarks

### Test Cases
1. "Show me tech companies" → discovers "Technology" sector
2. "Apple stock price" → maps to "AAPL"
3. "Large companies" → infers market cap threshold
4. "Last quarter" → resolves to date range
5. Empty result → diagnoses and corrects

## Success Metrics

1. **Value Resolution Rate**: % of user terms successfully mapped
2. **Self-Correction Success**: % of empty results fixed automatically
3. **Query Success Rate**: % of queries returning meaningful results
4. **Learning Effectiveness**: Reduction in correction needs over time
5. **Performance Impact**: Query latency with agentic features

## Deployment Strategy

1. **Feature Flag**: Deploy behind feature flag for gradual rollout
2. **A/B Testing**: Compare success rates with/without agentic features
3. **Monitoring**: Track all agent decisions and corrections
4. **Fallback**: Always have non-agentic path available

## Next Steps

1. Review and approve implementation plan
2. Set up development branch
3. Create test database with diverse values
4. Implement Phase 1 (Value Discovery)
5. Weekly demos of progress

This implementation plan provides a concrete path to building the agentic query system while maintaining the existing functionality.