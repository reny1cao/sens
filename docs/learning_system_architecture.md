# SENS Learning System Architecture

## System Components and Data Flow

```mermaid
graph TB
    subgraph "User Interface"
        A[User Query]
    end

    subgraph "Agent Pipeline"
        B[AgentNL2SQLPipeline]
        C[start_learning_session]
        D[get_relevant_knowledge]
        E[finish_learning_session]
    end

    subgraph "Agent Processing"
        F[EventEmittingLangGraphAgent]
        G[Agent Events]
        H[Event Handler]
    end

    subgraph "Learning System"
        I[APIBasedLearningSystem]
        J[LearningExperience]
        K[to_natural_text]
    end

    subgraph "LightRAG Server"
        L[LightRAGAPIClient]
        M[Knowledge Storage]
        N[Knowledge Retrieval]
        O[Knowledge Graph]
    end

    subgraph "Database"
        P[Query Execution]
        Q[Results]
    end

    A --> B
    B --> C
    C --> D
    D --> N
    N --> L
    L --> D
    D --> B
    B --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
    L --> M
    M --> O
    B --> E
    E --> I
    B --> P
    P --> Q
    Q --> B

    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style I fill:#e8f5e8
    style L fill:#fff3e0
    style O fill:#ffebee
```

## Learning Workflow Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant P as Pipeline
    participant L as Learning System
    participant A as Agent
    participant R as LightRAG
    participant K as Knowledge Graph

    U->>P: "Show me large tech companies"
    P->>L: start_learning_session()
    P->>L: get_relevant_knowledge()
    L->>R: query(enhanced_query)
    R->>L: relevant_knowledge
    L->>P: knowledge_text
    P->>A: process_query(enhanced_question)

    loop Agent Processing
        A->>A: reasoning_step()
        A->>P: emit_event(reasoning)
        P->>L: record_agent_event()
        A->>A: action_step()
        A->>P: emit_event(action)
        P->>L: record_agent_event()
        A->>A: observation_step()
        A->>P: emit_event(observation)
        P->>L: record_agent_event()
    end

    A->>P: final_result
    P->>L: finish_learning_session(outcome)
    L->>L: create_experience()
    L->>L: to_natural_text()
    L->>R: insert_text(experience)
    R->>K: update_knowledge_graph()
    P->>U: query_result
```

## Event Recording Process

```mermaid
graph LR
    subgraph "Agent Events"
        A1[reasoning_start]
        A2[reasoning]
        A3[exploration_start]
        A4[exploration]
        A5[sql_generation_start]
        A6[sql_generated]
        A7[execution_start]
        A8[execution]
        A9[answer_generated]
    end

    subgraph "Event Processing"
        B1[Event Handler]
        B2[record_agent_event]
        B3[Event Classification]
    end

    subgraph "Experience Building"
        C1[thinking_steps]
        C2[actions_taken]
        C3[outcome]
        C4[LearningExperience]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1
    A5 --> B1
    A6 --> B1
    A7 --> B1
    A8 --> B1
    A9 --> B1

    B1 --> B2
    B2 --> B3

    B3 --> C1
    B3 --> C2
    B3 --> C3

    C1 --> C4
    C2 --> C4
    C3 --> C4

    style A1 fill:#e3f2fd
    style A2 fill:#e3f2fd
    style A3 fill:#e8f5e8
    style A4 fill:#e8f5e8
    style A5 fill:#fff3e0
    style A6 fill:#fff3e0
    style A7 fill:#ffebee
    style A8 fill:#ffebee
    style A9 fill:#f3e5f5
```

## Knowledge Retrieval Process

```mermaid
graph TB
    subgraph "Query Analysis"
        A[New User Query]
        B[Extract Context]
        C[Enhance Query]
    end

    subgraph "Knowledge Search"
        D[LightRAG Query]
        E[Hybrid Search]
        F[Similarity Matching]
        G[Context Filtering]
    end

    subgraph "Knowledge Processing"
        H[Relevant Experiences]
        I[Pattern Extraction]
        J[Confidence Scoring]
        K[Knowledge Synthesis]
    end

    subgraph "Application"
        L[Enhanced Question]
        M[Agent Processing]
        N[Improved Results]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
    L --> M
    M --> N

    style A fill:#e1f5fe
    style D fill:#fff3e0
    style H fill:#e8f5e8
    style L fill:#f3e5f5
```

## Experience Storage Format

```mermaid
graph TB
    subgraph "Raw Experience"
        A[Query Text]
        B[Context Dict]
        C[Thinking Steps]
        D[Actions Taken]
        E[Outcome Dict]
    end

    subgraph "Natural Language Conversion"
        F[LEARNING EXPERIENCE Header]
        G[SESSION & TIMESTAMP]
        H[CONTEXT Section]
        I[THINKING PROCESS]
        J[ACTIONS TAKEN]
        K[OUTCOME Section]
    end

    subgraph "LightRAG Storage"
        L[Text Document]
        M[Embeddings]
        N[Knowledge Graph Nodes]
        O[Relationships]
    end

    A --> F
    B --> G
    B --> H
    C --> I
    D --> J
    E --> K

    F --> L
    G --> L
    H --> L
    I --> L
    J --> L
    K --> L

    L --> M
    L --> N
    N --> O

    style A fill:#e3f2fd
    style F fill:#e8f5e8
    style L fill:#fff3e0
    style N fill:#ffebee
```

## Learning Patterns Discovery

```mermaid
graph LR
    subgraph "User Terms"
        A1["large tech companies"]
        A2["biggest technology firms"]
        A3["top tech stocks"]
        A4["FAANG companies"]
    end

    subgraph "Learning Process"
        B1[Query Processing]
        B2[Value Discovery]
        B3[Pattern Recognition]
        B4[Mapping Creation]
    end

    subgraph "Database Mappings"
        C1["sector='Technology'"]
        C2["market_cap > 500B"]
        C3["ORDER BY market_cap DESC"]
        C4["symbol IN ('AAPL', 'GOOGL', ...)"]
    end

    subgraph "Learned Patterns"
        D1[Value Mappings]
        D2[Query Templates]
        D3[Success Patterns]
        D4[Error Corrections]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B1

    B1 --> B2
    B2 --> B3
    B3 --> B4

    B4 --> C1
    B4 --> C2
    B4 --> C3
    B4 --> C4

    C1 --> D1
    C2 --> D1
    C3 --> D2
    C4 --> D3

    style A1 fill:#e3f2fd
    style B2 fill:#e8f5e8
    style C1 fill:#fff3e0
    style D1 fill:#ffebee
```

## Performance Improvement Cycle

```mermaid
graph TB
    subgraph "Cold Query (First Time)"
        A1[User Query]
        A2[No Prior Knowledge]
        A3[Full Exploration]
        A4[3-5 Iterations]
        A5[5-10 Seconds]
        A6[70% Success Rate]
    end

    subgraph "Learning Process"
        B1[Record Experience]
        B2[Extract Patterns]
        B3[Store Knowledge]
        B4[Build Mappings]
    end

    subgraph "Warm Query (Subsequent)"
        C1[Similar Query]
        C2[Retrieve Knowledge]
        C3[Apply Patterns]
        C4[1-2 Iterations]
        C5[1-2 Seconds]
        C6[90%+ Success Rate]
    end

    A1 --> A2
    A2 --> A3
    A3 --> A4
    A4 --> A5
    A5 --> A6

    A6 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> B4

    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C5 --> C6

    B4 --> C2

    style A1 fill:#ffebee
    style B1 fill:#e8f5e8
    style C1 fill:#e1f5fe
    style C6 fill:#e8f5e8
```

## Architecture Benefits

### 1. **Continuous Learning**
- Every query becomes a learning opportunity
- Patterns are extracted and stored automatically
- Knowledge base grows with usage

### 2. **Contextual Understanding**
- Database-specific knowledge is maintained
- User domain terminology is learned
- Business context is preserved

### 3. **Performance Optimization**
- Repeated patterns are cached
- Successful queries are templates for new ones
- Error corrections are remembered

### 4. **Scalable Knowledge**
- Knowledge graph scales with usage
- Cross-session learning benefits all users
- Domain expertise accumulates over time

### 5. **Self-Improvement**
- System gets better with every interaction
- Failure analysis improves future success
- User feedback refines understanding

## Technical Implementation

### Core Classes

1. **APIBasedLearningSystem**
   - Orchestrates the learning workflow
   - Manages session lifecycle
   - Interfaces with LightRAG API

2. **LearningExperience**
   - Encapsulates a complete query experience
   - Converts to natural language for storage
   - Preserves context and outcomes

3. **LightRAGAPIClient**
   - Handles all LightRAG server communication
   - Manages document insertion and retrieval
   - Provides health monitoring

4. **EventEmittingLangGraphAgent**
   - Emits events during agent processing
   - Provides real-time monitoring
   - Enables learning system integration

### Integration Points

- **Pipeline Integration**: Seamless integration with existing AgentNL2SQLPipeline
- **Event Handling**: Automatic event recording without code changes
- **Knowledge Application**: Transparent knowledge retrieval and application
- **Performance Monitoring**: Built-in analytics and metrics

This architecture creates a self-improving system that becomes more intelligent and efficient with every query processed.
