# SENS Roadmap: From NL2SQL to Proactive Data Intelligence Platform

## Vision
Transform SENS from a reactive query tool into a proactive data intelligence platform that anticipates user needs and delivers insights before questions are asked.

> **Note**: This roadmap now incorporates the Agentic Query Architecture. See [agentic_query_architecture.md](./docs/agentic_query_architecture.md) for detailed design of the intelligent query understanding system that forms the foundation of Phase 1.

## Current State Analysis

### Strengths
- **Solid Architecture**: Clean separation of concerns with modular design
- **Advanced Retrieval**: Dual token/embedding search with schema understanding
- **Safety First**: Comprehensive validation pipeline
- **Session Management**: Redis-backed conversations with state tracking
- **Extensible Design**: Ready for plugin architecture

### Technical Debt & Immediate Fixes
1. **Schema Context Mismatch** ✅ (PR #23)
2. **Test Coverage**: Currently ~16%, need to reach 80%+
3. **Performance**: Embedding search takes 20+ seconds
4. **Error Handling**: Better user-facing error messages needed

## Implementation Phases

### Phase 0: Foundation Strengthening (Weeks 1-4) ✅
**Goal**: Stabilize and optimize current system

#### Week 1-2: Core Infrastructure ✅
```python
# Completed
- [x] Comprehensive data loading system (100+ securities, ETFs, indicators)
- [x] Progress tracking and resumable data loading
- [x] Sample data generation for portfolios, options, market data
- [x] Documentation for data loading process
```

#### Week 3-4: Testing & Documentation
```python
# Priority: Achieve 80% test coverage
- [ ] Add integration tests for all API endpoints
- [ ] Performance benchmarking suite
- [ ] Load testing for concurrent users
- [x] Data loading documentation
```

### Phase 1: Agentic Query Intelligence (Weeks 5-14)
**Goal**: Build intelligent query understanding with value discovery and self-correction

#### Component 1: Query Planning Agent
```python
class QueryPlanningAgent:
    """ReAct-style agent for intelligent query planning."""
    
    async def plan_query(self, user_input: str) -> QueryPlan:
        """
        Use reasoning and tools to understand user intent.
        
        Example:
        User: "Show me tech giants' performance"
        
        Thought 1: Need to map "tech giants" to database values
        Action 1: SearchDatabaseValues(table="securities", column="company_name")
        Observation 1: Found AAPL, GOOGL, MSFT, META, NVDA in Technology sector
        
        Thought 2: Define "giants" using market cap distribution
        Action 2: GetValueStatistics(table="securities", column="market_cap")
        Observation 2: Top tech companies have market_cap > $500B
        
        Final Plan: Query for Technology sector with market_cap > $500B
        """
```

#### Component 2: Value Discovery System
```python
class ValueDiscoverySystem:
    """Tools for exploring and mapping database values."""
    
    async def discover_values(self, user_term: str) -> ValueMapping:
        # Search across columns for similar values
        candidates = await self.similarity_search(user_term)
        
        # Use LLM to validate mappings
        validated = await self.validate_mappings(user_term, candidates)
        
        # Learn from successful mappings
        await self.update_value_index(user_term, validated)
        
        return validated
```

#### Component 3: Self-Correcting Executor
```python
class SelfCorrectingExecutor:
    """Execute queries with automatic error recovery."""
    
    async def execute_with_correction(self, sql: str) -> QueryResult:
        result = await self.execute(sql)
        
        if result.is_empty():
            # Diagnose why query returned no results
            diagnosis = await self.diagnose_empty_result(sql)
            
            # Apply corrections based on diagnosis
            if diagnosis.type == "value_mismatch":
                sql = await self.fix_value_mismatches(sql)
            elif diagnosis.type == "date_range_issue":
                sql = await self.expand_date_range(sql)
            elif diagnosis.type == "join_issue":
                sql = await self.fix_joins(sql)
                
            # Retry with corrected query
            result = await self.execute(sql)
            
        return result
```

#### Component 4: Result Enhancement Engine
```python
class ResultEnhancer:
    """Add statistical analysis and insights to query results."""

    def enhance(self, query_result: QueryResult) -> EnhancedResult:
        return EnhancedResult(
            data=query_result.data,
            summary=self._generate_summary(query_result),
            statistics=self._calculate_statistics(query_result),
            trends=self._detect_trends(query_result),
            anomalies=self._find_anomalies(query_result),
            visualizations=self._create_charts(query_result)
        )
```

#### Component 2: Query Chain Executor
```python
class QueryChainExecutor:
    """Execute multi-step analytical workflows."""

    async def execute_chain(self, initial_query: str) -> ChainResult:
        # Break complex questions into steps
        steps = await self.query_planner.plan(initial_query)

        # Execute each step
        results = []
        for step in steps:
            result = await self.execute_step(step, results)
            results.append(result)

        # Combine and analyze
        return await self.synthesize_results(results)
```

#### Deliverables:
- [ ] ReAct-based query planning agent
- [ ] Value discovery and mapping system
- [ ] Self-correcting query executor
- [ ] Cross-column value search index
- [ ] Learning value mapper with confidence scoring
- [ ] Statistical summaries for all queries
- [ ] Trend detection in time-series data
- [ ] Multi-step query execution
- [ ] Export to Excel/CSV with insights
- [ ] Basic visualization support

### Phase 2: Behavioral Learning System (Weeks 15-22)
**Goal**: Understand user patterns and preferences

#### Component 1: User Behavior Tracker
```python
class UserBehaviorTracker:
    """Track and learn from user interactions."""

    def __init__(self):
        self.event_store = EventStore()
        self.pattern_detector = PatternDetector()
        self.preference_learner = PreferenceLearner()

    async def track_event(self, user_id: str, event: Event):
        # Store raw event
        await self.event_store.append(user_id, event)

        # Update patterns in real-time
        patterns = await self.pattern_detector.update(user_id, event)

        # Adjust preferences
        await self.preference_learner.learn(user_id, patterns)
```

#### Component 2: Query Pattern Analyzer
```python
class QueryPatternAnalyzer:
    """Identify recurring query patterns and interests."""

    def analyze_patterns(self, user_id: str) -> UserPatterns:
        return UserPatterns(
            temporal_patterns=self._find_time_patterns(user_id),
            topic_interests=self._extract_topics(user_id),
            query_sequences=self._find_sequences(user_id),
            data_preferences=self._identify_preferences(user_id)
        )
```

#### Deliverables:
- [ ] Event tracking system
- [ ] User profile builder
- [ ] Query pattern detection
- [ ] Preference learning algorithm
- [ ] Privacy-compliant data storage

### Phase 3: Proactive Monitoring Engine (Weeks 23-34)
**Goal**: Monitor data continuously and generate insights

#### Component 1: Change Detection System
```python
class ChangeDetectionSystem:
    """Monitor data changes and trigger analysis."""

    def __init__(self):
        self.cdc_engine = ChangeDataCapture()
        self.relevance_scorer = RelevanceScorer()
        self.alert_manager = AlertManager()

    async def monitor(self):
        async for change in self.cdc_engine.stream():
            # Score relevance for each user
            relevance_scores = await self.relevance_scorer.score(change)

            # Trigger alerts for high-relevance changes
            for user_id, score in relevance_scores.items():
                if score > user.threshold:
                    await self.alert_manager.notify(user_id, change)
```

#### Component 2: Insight Generation Pipeline
```python
class InsightGenerator:
    """Generate proactive insights from data patterns."""

    async def generate_insights(self, context: Context) -> List[Insight]:
        insights = []

        # Anomaly detection
        anomalies = await self.detect_anomalies(context)
        insights.extend(self._narrate_anomalies(anomalies))

        # Trend analysis
        trends = await self.analyze_trends(context)
        insights.extend(self._narrate_trends(trends))

        # Predictive insights
        predictions = await self.predict_future(context)
        insights.extend(self._narrate_predictions(predictions))

        # Correlation discovery
        correlations = await self.find_correlations(context)
        insights.extend(self._narrate_correlations(correlations))

        return insights
```

#### Component 3: Smart Notification System
```python
class SmartNotificationSystem:
    """Deliver insights at the right time through the right channel."""

    def __init__(self):
        self.channels = {
            'websocket': WebSocketChannel(),
            'email': EmailChannel(),
            'slack': SlackChannel(),
            'in_app': InAppChannel()
        }
        self.scheduler = NotificationScheduler()
        self.fatigue_manager = FatigueManager()

    async def notify(self, user_id: str, insight: Insight):
        # Check if we should notify
        if not self.fatigue_manager.should_notify(user_id, insight):
            return

        # Select best channel and time
        channel = self.select_channel(user_id, insight)
        send_time = self.scheduler.optimal_time(user_id, insight)

        # Schedule notification
        await self.schedule_notification(channel, send_time, insight)
```

#### Deliverables:
- [ ] Real-time data monitoring
- [ ] Anomaly detection system
- [ ] Trend analysis engine
- [ ] Correlation discovery
- [ ] Multi-channel notifications
- [ ] Notification fatigue management

### Phase 4: Conversational Intelligence (Weeks 35-42)
**Goal**: Natural, contextual interactions with insights

#### Component 1: Conversational Insight Narrator
```python
class InsightNarrator:
    """Convert data insights into natural conversations."""

    def narrate(self, insight: Insight, user_context: UserContext) -> str:
        # Personalize based on user knowledge
        narrative = self.personalize(insight, user_context)

        # Add relevant context
        narrative = self.add_context(narrative, user_context)

        # Make it conversational
        narrative = self.conversationalize(narrative)

        # Add actionable suggestions
        narrative = self.add_actions(narrative, insight)

        return narrative
```

#### Component 2: Interactive Insight Explorer
```python
class InteractiveInsightExplorer:
    """Allow users to explore insights through conversation."""

    async def explore(self, insight: Insight, user_query: str) -> Response:
        # Understand follow-up question
        intent = await self.understand_intent(user_query, insight)

        # Drill down into data
        if intent.type == "drill_down":
            return await self.drill_down(insight, intent.parameters)

        # Explain reasoning
        elif intent.type == "explain":
            return await self.explain_insight(insight, intent.focus)

        # Compare with history
        elif intent.type == "compare":
            return await self.compare_historical(insight, intent.period)
```

#### Deliverables:
- [ ] Natural language generation for insights
- [ ] Conversational context management
- [ ] Interactive insight exploration
- [ ] Voice interface support (future)

### Phase 5: Self-Improving Platform (Weeks 43-54)
**Goal**: System that learns and improves autonomously

#### Component 1: Feedback Learning System
```python
class FeedbackLearner:
    """Learn from user feedback to improve insights."""

    async def learn_from_feedback(self, feedback: Feedback):
        # Update insight quality model
        await self.quality_model.update(feedback)

        # Adjust relevance scoring
        await self.relevance_model.adjust(feedback)

        # Improve narrative generation
        await self.narrative_model.learn(feedback)

        # Retrain anomaly detection
        if feedback.type == "false_positive":
            await self.anomaly_model.retrain(feedback.context)
```

#### Component 2: Automated Optimization
```python
class AutoOptimizer:
    """Automatically optimize system performance."""

    async def optimize(self):
        # Query performance optimization
        slow_queries = await self.identify_slow_queries()
        await self.suggest_indexes(slow_queries)

        # Schema understanding improvement
        missing_relationships = await self.find_missing_relationships()
        await self.update_schema_graph(missing_relationships)

        # Retrieval accuracy enhancement
        retrieval_failures = await self.analyze_retrieval_failures()
        await self.improve_retrieval(retrieval_failures)
```

#### Deliverables:
- [ ] Feedback collection system
- [ ] ML model retraining pipeline
- [ ] Automated performance optimization
- [ ] Self-documenting features
- [ ] A/B testing framework

## Technical Infrastructure Requirements

### 1. Data Layer Enhancements
```yaml
Components:
  - Change Data Capture (CDC) system
  - Time-series database (InfluxDB/TimescaleDB)
  - Feature store for ML features
  - Event streaming (Kafka/Redis Streams)
```

### 2. Processing Layer
```yaml
Components:
  - Distributed task queue (Celery)
  - Stream processing (Flink/Spark Streaming)
  - ML model serving (MLflow/Seldon)
  - Workflow orchestration (Airflow/Prefect)
```

### 3. Delivery Layer
```yaml
Components:
  - WebSocket server for real-time
  - Notification service
  - API Gateway enhancements
  - Mobile app support
```

## Metrics for Success

### Phase 1 Metrics
- Query response time < 3 seconds
- Test coverage > 80%
- User satisfaction > 4.5/5

### Phase 2 Metrics
- Pattern detection accuracy > 85%
- User engagement increase > 30%
- Query success rate > 95%

### Phase 3 Metrics
- Proactive insight relevance > 70%
- Notification engagement > 40%
- Time-to-insight reduction > 50%

### Phase 4 Metrics
- Conversation completion rate > 80%
- Insight exploration depth > 3 levels
- Natural language quality score > 4/5

### Phase 5 Metrics
- System self-improvement rate > 5%/month
- Autonomous optimization success > 90%
- User retention > 85%

## Risk Mitigation

### Technical Risks
1. **Scalability**: Design for horizontal scaling from day 1
2. **Privacy**: Implement privacy-by-design principles
3. **Model Drift**: Continuous monitoring and retraining
4. **Integration Complexity**: Modular architecture with clear interfaces

### Business Risks
1. **User Adoption**: Gradual rollout with power users
2. **Information Overload**: Smart notification fatigue management
3. **Trust**: Explainable AI and transparency
4. **Cost**: Optimize LLM usage and caching

## Next Immediate Steps

### Week 1 Tasks
1. [ ] Set up performance monitoring
2. [ ] Create benchmarking suite
3. [ ] Implement basic caching layer
4. [ ] Design event tracking schema

### Week 2 Tasks
1. [ ] Build result enhancement prototype
2. [ ] Create user behavior tracking tables
3. [ ] Implement basic anomaly detection
4. [ ] Set up A/B testing framework

### Week 3 Tasks
1. [ ] Deploy monitoring infrastructure
2. [ ] Create first proactive insight prototype
3. [ ] Build notification system foundation
4. [ ] Implement feedback collection

## Conclusion

This roadmap transforms SENS from a reactive query tool into a proactive intelligence platform. The key is maintaining the elegant architecture while gradually adding intelligence layers. Each phase builds on the previous, creating a compound effect of value delivery.

The future of SENS is not just answering questions - it's knowing what questions to ask before users even think of them.
