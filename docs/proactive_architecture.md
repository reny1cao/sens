# Proactive Intelligence Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User Interface Layer                           │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│   Web App   │  Mobile App │   Slack Bot │  Email Svc  │   API Gateway  │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴──────┬─────────┘
       │             │             │             │             │
       └─────────────┴─────────────┴─────────────┴─────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │  Notification Hub  │
                          └─────────┬─────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│                        Proactive Intelligence Layer                      │
├─────────────────┬─────────────────┬─────────────────┬─────────────────┤
│ Insight Engine  │ Pattern Detector │ Anomaly Detector│ Trend Analyzer  │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ User Profiler   │ Query Predictor  │ Alert Manager   │ ML Models       │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│                           Processing Layer                               │
├─────────────────┬─────────────────┬─────────────────┬─────────────────┤
│ Event Processor │ Stream Analytics │ Batch Analytics │ Task Queue      │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│                            Data Layer                                    │
├──────────────┬──────────────┬──────────────┬──────────────┬───────────┤
│   Primary DB │ Time Series  │ Event Store  │    Cache     │  Feature   │
│ (PostgreSQL) │  (InfluxDB)  │(Event Store) │   (Redis)    │   Store    │
└──────────────┴──────────────┴──────────────┴──────────────┴───────────┘
```

## Data Flow for Proactive Insights

### 1. Continuous Monitoring Flow

```
Database Changes ─────┐
                      ├──> Change Data Capture ──> Event Stream
User Interactions ────┤                                │
                      │                                ▼
External Events ──────┘                         Event Processor
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                              Pattern Detector  Anomaly Detector  Trend Analyzer
                                    │                 │                 │
                                    └─────────────────┴─────────────────┘
                                                      │
                                                      ▼
                                              Relevance Scorer
                                                      │
                                                      ▼
                                              User Context Matcher
                                                      │
                                                      ▼
                                              Insight Generator
                                                      │
                                                      ▼
                                              Notification Engine
```

### 2. User Learning Flow

```
User Query ──────> Query Analyzer ──────> Intent + Context
    │                                            │
    ▼                                            ▼
Event Tracker                              Pattern Storage
    │                                            │
    ▼                                            ▼
User Profile ←─────── Pattern Learner ←─────────┘
    │
    ▼
Personalization Engine
    │
    ├──> Query Suggestions
    ├──> Relevance Tuning
    └──> Notification Preferences
```

## Component Specifications

### 1. Change Data Capture (CDC)

```python
class ChangeDataCapture:
    """Capture and stream database changes."""

    def __init__(self, db_config: DatabaseConfig):
        self.wal_reader = WALReader(db_config)
        self.change_stream = ChangeStream()
        self.filters = ChangeFilters()

    async def start_capture(self):
        async for change in self.wal_reader.read():
            # Filter relevant changes
            if self.filters.is_relevant(change):
                # Enrich with metadata
                enriched = await self.enrich_change(change)

                # Publish to stream
                await self.change_stream.publish(enriched)

    async def enrich_change(self, change: Change) -> EnrichedChange:
        return EnrichedChange(
            change=change,
            timestamp=datetime.utcnow(),
            table_metadata=self.get_table_metadata(change.table),
            impact_analysis=await self.analyze_impact(change)
        )
```

### 2. Event Stream Processing

```python
class EventStreamProcessor:
    """Process events in real-time for insights."""

    def __init__(self):
        self.processors = {
            'database_change': DatabaseChangeProcessor(),
            'user_query': UserQueryProcessor(),
            'external_event': ExternalEventProcessor()
        }
        self.aggregators = {
            '1min': MinuteAggregator(),
            '5min': FiveMinuteAggregator(),
            '1hour': HourlyAggregator()
        }

    async def process_stream(self, event_stream: AsyncIterator[Event]):
        async for event in event_stream:
            # Route to appropriate processor
            processor = self.processors.get(event.type)
            if processor:
                processed = await processor.process(event)

                # Update aggregations
                for aggregator in self.aggregators.values():
                    await aggregator.update(processed)

                # Check for insights
                insights = await self.check_insights(processed)
                if insights:
                    await self.publish_insights(insights)
```

### 3. Pattern Detection Engine

```python
class PatternDetector:
    """Detect patterns in data and user behavior."""

    def __init__(self):
        self.detectors = {
            'temporal': TemporalPatternDetector(),
            'sequential': SequentialPatternDetector(),
            'behavioral': BehavioralPatternDetector(),
            'anomaly': AnomalyPatternDetector()
        }
        self.pattern_store = PatternStore()

    async def detect_patterns(self, data: TimeSeriesData) -> List[Pattern]:
        patterns = []

        for detector_name, detector in self.detectors.items():
            try:
                detected = await detector.detect(data)
                patterns.extend(detected)
            except Exception as e:
                log.error(f"Pattern detection failed: {detector_name}", error=e)

        # Store significant patterns
        significant = [p for p in patterns if p.confidence > 0.7]
        await self.pattern_store.store(significant)

        return significant
```

### 4. Anomaly Detection System

```python
class AnomalyDetector:
    """Detect anomalies using multiple algorithms."""

    def __init__(self):
        self.algorithms = {
            'isolation_forest': IsolationForestDetector(),
            'lstm_autoencoder': LSTMAutoencoderDetector(),
            'statistical': StatisticalAnomalyDetector(),
            'prophet': ProphetAnomalyDetector()
        }
        self.ensemble = AnomalyEnsemble(self.algorithms)

    async def detect_anomalies(self, data: pd.DataFrame) -> List[Anomaly]:
        # Run all detectors in parallel
        results = await asyncio.gather(*[
            algo.detect(data) for algo in self.algorithms.values()
        ])

        # Ensemble voting
        anomalies = self.ensemble.vote(results)

        # Enrich with context
        enriched = []
        for anomaly in anomalies:
            context = await self.get_anomaly_context(anomaly, data)
            enriched.append(anomaly.with_context(context))

        return enriched
```

### 5. Insight Generation Pipeline

```python
class InsightGenerator:
    """Generate actionable insights from patterns and anomalies."""

    def __init__(self):
        self.generators = {
            'anomaly': AnomalyInsightGenerator(),
            'trend': TrendInsightGenerator(),
            'correlation': CorrelationInsightGenerator(),
            'prediction': PredictiveInsightGenerator()
        }
        self.llm_narrator = LLMNarrator()
        self.action_suggester = ActionSuggester()

    async def generate_insights(
        self,
        patterns: List[Pattern],
        anomalies: List[Anomaly],
        context: Context
    ) -> List[Insight]:
        insights = []

        # Generate raw insights
        for pattern in patterns:
            generator = self.generators.get(pattern.type)
            if generator:
                raw_insight = await generator.generate(pattern, context)
                insights.append(raw_insight)

        # Narrate insights
        narrated = []
        for insight in insights:
            narrative = await self.llm_narrator.narrate(insight, context)
            actions = await self.action_suggester.suggest(insight, context)

            narrated.append(
                NarratedInsight(
                    insight=insight,
                    narrative=narrative,
                    suggested_actions=actions
                )
            )

        return narrated
```

### 6. User Context Engine

```python
class UserContextEngine:
    """Maintain and update user context for personalization."""

    def __init__(self):
        self.profile_store = UserProfileStore()
        self.preference_learner = PreferenceLearner()
        self.context_builder = ContextBuilder()

    async def get_user_context(self, user_id: str) -> UserContext:
        # Load base profile
        profile = await self.profile_store.get(user_id)

        # Add current context
        current_context = await self.context_builder.build_current(user_id)

        # Predict immediate needs
        predicted_needs = await self.predict_needs(profile, current_context)

        return UserContext(
            profile=profile,
            current=current_context,
            predicted_needs=predicted_needs,
            notification_preferences=profile.notification_preferences,
            relevance_thresholds=profile.relevance_thresholds
        )

    async def update_from_interaction(
        self,
        user_id: str,
        interaction: Interaction
    ):
        # Update profile
        profile = await self.profile_store.get(user_id)
        profile = await self.preference_learner.learn(profile, interaction)
        await self.profile_store.save(profile)

        # Update prediction models
        await self.update_prediction_models(user_id, interaction)
```

### 7. Notification Orchestrator

```python
class NotificationOrchestrator:
    """Intelligently deliver notifications across channels."""

    def __init__(self):
        self.channels = {
            'in_app': InAppNotificationChannel(),
            'email': EmailNotificationChannel(),
            'slack': SlackNotificationChannel(),
            'sms': SMSNotificationChannel(),
            'push': PushNotificationChannel()
        }
        self.scheduler = NotificationScheduler()
        self.fatigue_manager = FatigueManager()
        self.priority_calculator = PriorityCalculator()

    async def notify(
        self,
        user_id: str,
        insight: Insight,
        context: UserContext
    ):
        # Check notification fatigue
        if await self.fatigue_manager.is_fatigued(user_id):
            await self.queue_for_digest(user_id, insight)
            return

        # Calculate priority
        priority = await self.priority_calculator.calculate(
            insight,
            context
        )

        # Select channel based on priority and preferences
        channel = self.select_channel(priority, context.notification_preferences)

        # Schedule or send immediately
        if priority.is_urgent:
            await self.send_immediate(channel, user_id, insight)
        else:
            optimal_time = await self.scheduler.find_optimal_time(
                user_id,
                priority
            )
            await self.schedule_notification(
                channel,
                user_id,
                insight,
                optimal_time
            )
```

## Data Models

### 1. Insight Model

```python
@dataclass
class Insight:
    id: str
    type: InsightType
    severity: Severity
    confidence: float
    title: str
    description: str
    data_points: List[DataPoint]
    pattern: Optional[Pattern]
    anomaly: Optional[Anomaly]
    affected_metrics: List[str]
    time_range: TimeRange
    created_at: datetime
    expires_at: Optional[datetime]

    def to_notification(self) -> NotificationContent:
        return NotificationContent(
            title=self.title,
            body=self.description,
            data=self.get_key_data_points(),
            actions=self.get_suggested_actions(),
            urgency=self.calculate_urgency()
        )
```

### 2. User Profile Model

```python
@dataclass
class UserProfile:
    user_id: str
    created_at: datetime
    last_active: datetime

    # Behavioral patterns
    query_patterns: List[QueryPattern]
    temporal_patterns: TemporalPatterns
    interest_topics: List[Topic]

    # Preferences
    notification_preferences: NotificationPreferences
    relevance_thresholds: Dict[InsightType, float]
    preferred_visualizations: List[VisualizationType]

    # Learning data
    interaction_history: List[Interaction]
    feedback_history: List[Feedback]
    decision_patterns: List[DecisionPattern]

    # Computed fields
    engagement_score: float
    expertise_level: ExpertiseLevel
    preferred_complexity: ComplexityLevel
```

### 3. Pattern Model

```python
@dataclass
class Pattern:
    id: str
    type: PatternType
    confidence: float
    support: float  # How often this pattern occurs
    lift: float     # How much more likely than random

    # Pattern details
    sequence: Optional[List[Event]]
    temporal_info: Optional[TemporalInfo]
    conditions: List[Condition]

    # Metadata
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    affected_entities: List[str]

    def is_significant(self) -> bool:
        return (
            self.confidence > 0.7 and
            self.support > 0.1 and
            self.lift > 1.5
        )
```

## Implementation Priorities

### Phase 1: Foundation (Weeks 1-4)
1. Set up event streaming infrastructure
2. Implement basic CDC for PostgreSQL
3. Create user profile storage
4. Build simple pattern detection

### Phase 2: Intelligence (Weeks 5-8)
1. Implement anomaly detection algorithms
2. Build insight generation pipeline
3. Create narrative generation with LLM
4. Develop relevance scoring

### Phase 3: Delivery (Weeks 9-12)
1. Build notification orchestrator
2. Implement fatigue management
3. Create channel integrations
4. Develop scheduling algorithm

### Phase 4: Learning (Weeks 13-16)
1. Implement feedback loop
2. Build preference learning
3. Create A/B testing framework
4. Develop model retraining pipeline

## Success Metrics

```python
class ProactiveMetrics:
    """Track success of proactive features."""

    METRICS = {
        "insight_relevance": {
            "target": 0.75,
            "formula": "clicked_insights / delivered_insights"
        },
        "proactive_engagement": {
            "target": 0.40,
            "formula": "proactive_interactions / total_interactions"
        },
        "time_to_action": {
            "target": 300,  # 5 minutes
            "formula": "avg(action_time - notification_time)"
        },
        "notification_fatigue": {
            "target": 0.10,
            "formula": "unsubscribes / total_users"
        },
        "insight_accuracy": {
            "target": 0.85,
            "formula": "confirmed_insights / total_insights"
        }
    }
```

This architecture provides a robust foundation for building proactive intelligence into SENS while maintaining scalability and reliability.
