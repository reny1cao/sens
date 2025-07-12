# Agent Memory System Integration Plan

## 🎯 Overview
This document outlines how to integrate the KuzuDB-based agent memory system across all SENS agent systems beyond the CLI.

## 🏗️ Architecture Integration Points

### 1. **API Integration (FastAPI)**

#### A. Update Agent Stream Router
```python
# src/sens/api/routers/agent_stream.py
from sens.memory import AgentMemory, AgentMemoryTools

async def generate_agent_stream(
    query: str,
    max_iterations: int = 10,
    session_id: str = None,
    memory_enabled: bool = True,
    database_context: str = None
) -> AsyncGenerator[str, None]:

    # Initialize memory system
    memory = AgentMemory(db_path=f"api_memory_{session_id}.db")
    memory_tools = AgentMemoryTools(memory)

    # Initialize agent with memory
    agent = EventEmittingAgent(
        tools=tools,
        memory=memory,
        reasoning_engine=reasoning_engine,
        max_iterations=max_iterations,
    )

    # Add memory tools to agent
    agent.tools.remember_concept = memory_tools.remember_concept
    agent.tools.remember_pattern = memory_tools.remember_pattern
    # ... other memory tools

    # Stream memory events
    yield f"event: memory_recall\ndata: {json.dumps(memory_stats)}\n\n"
```

#### B. New Memory Management Endpoints
```python
# src/sens/api/routers/memory.py
@router.get("/memory/stats")
async def get_memory_stats(session_id: str):
    """Get memory statistics for a session"""

@router.post("/memory/search")
async def search_memories(query: str, session_id: str):
    """Search memories by content"""

@router.delete("/memory/{memory_id}")
async def forget_memory(memory_id: str, session_id: str):
    """Remove a specific memory"""
```

### 2. **Web Interface Integration**

#### A. React Components
```typescript
// web/hooks/useAgentMemory.ts
export const useAgentMemory = (sessionId: string) => {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);

  const searchMemories = async (query: string) => {
    const response = await fetch(`/api/memory/search`, {
      method: 'POST',
      body: JSON.stringify({ query, session_id: sessionId }),
    });
    return response.json();
  };

  const getMemoryStats = async () => {
    const response = await fetch(`/api/memory/stats?session_id=${sessionId}`);
    return response.json();
  };

  return { memories, memoryStats, searchMemories, getMemoryStats };
};
```

#### B. Memory Visualization Component
```typescript
// web/components/memory/MemoryGraph.tsx
interface MemoryGraphProps {
  sessionId: string;
  memories: Memory[];
  onMemorySelect: (memory: Memory) => void;
}

export const MemoryGraph: React.FC<MemoryGraphProps> = ({
  sessionId,
  memories,
  onMemorySelect
}) => {
  // D3.js or vis.js graph visualization
  // Show memory nodes and relationships
  // Interactive exploration of agent knowledge
};
```

### 3. **BIRD Evaluation Integration**

#### A. Enhanced BIRD Evaluation with Memory
```python
# src/sens/api/routers/bird_sql_dev_evaluation.py
class BirdSQLDevEvaluator:
    def __init__(self, memory_enabled: bool = True):
        self.memory_enabled = memory_enabled
        if memory_enabled:
            self.memory = AgentMemory(db_path="bird_evaluation_memory.db")
            self.memory_tools = AgentMemoryTools(self.memory)

    async def evaluate_with_memory(self, task: Dict) -> Dict:
        """Evaluate task with memory learning"""

        # Recall relevant knowledge
        if self.memory_enabled:
            memories = await self.memory_tools.recall_knowledge(
                query=task["question"],
                context={"database": task["db_id"]},
                limit=5
            )

            # Apply memory to task context
            task["memory_context"] = memories

        # Run evaluation
        result = await self.evaluate_task(task)

        # Learn from results
        if self.memory_enabled and result["success"]:
            await self._learn_from_success(task, result)

        return result

    async def _learn_from_success(self, task: Dict, result: Dict):
        """Learn from successful evaluation"""

        # Remember successful pattern
        await self.memory_tools.remember_pattern(
            name=f"bird_{task['db_id']}_{hash(task['question'])}",
            trigger_phrase=task["question"],
            sql_template=result["predicted_sql"],
            tables_used=result["tables_used"],
            success_context={
                "database": task["db_id"],
                "execution_accuracy": result["execution_accuracy"],
                "exact_match": result["exact_match"]
            }
        )
```

### 4. **Unified Evaluation with Memory**

#### A. Cross-Dataset Learning
```python
# src/sens/api/routers/unified_evaluation.py
class UnifiedEvaluationWithMemory:
    def __init__(self):
        # Shared memory across all evaluation types
        self.memory = AgentMemory(db_path="unified_evaluation_memory.db")
        self.memory_tools = AgentMemoryTools(self.memory)

    async def evaluate_bird_critic_with_memory(self, task: Dict):
        """BIRD-CRITIC evaluation with memory"""
        return await self._evaluate_with_memory(task, "bird_critic")

    async def evaluate_bird_sql_dev_with_memory(self, task: Dict):
        """BIRD-SQL-DEV evaluation with memory"""
        return await self._evaluate_with_memory(task, "bird_sql_dev")

    async def _evaluate_with_memory(self, task: Dict, evaluation_type: str):
        """Unified evaluation with memory learning"""

        # Cross-dataset memory recall
        memories = await self.memory_tools.recall_knowledge(
            query=task["question"],
            context={"evaluation_type": evaluation_type},
            limit=10
        )

        # Apply learned patterns from other datasets
        if memories.success:
            task["cross_dataset_patterns"] = memories.data["memories"]

        # Evaluate and learn
        result = await self._evaluate_task(task, evaluation_type)

        if result["success"]:
            await self._cross_dataset_learning(task, result, evaluation_type)

        return result
```

## 🔧 Implementation Strategy

### Phase 1: Core API Integration (Week 1-2)
1. ✅ Update agent stream router with memory
2. ✅ Add memory management endpoints
3. ✅ Implement session-based memory isolation
4. ✅ Add memory events to SSE streams

### Phase 2: Web Interface (Week 3-4)
1. ✅ Create memory visualization components
2. ✅ Add memory search and management UI
3. ✅ Integrate with existing query interfaces
4. ✅ Add memory performance analytics

### Phase 3: Evaluation Integration (Week 5-6)
1. ✅ Enhance BIRD evaluations with memory
2. ✅ Implement cross-dataset learning
3. ✅ Add memory-based performance metrics
4. ✅ Create evaluation memory analytics

### Phase 4: Advanced Features (Week 7-8)
1. ✅ Memory export/import capabilities
2. ✅ Memory clustering and analysis
3. ✅ A/B testing with/without memory
4. ✅ Production monitoring and alerts

## 🎯 Key Benefits

### For Users:
- **Faster Queries**: Reuse of learned patterns
- **Better Accuracy**: Cross-query learning
- **Transparent AI**: Visible reasoning process
- **Personalized Experience**: Session-based learning

### For Developers:
- **Modular Design**: Easy integration
- **Performance Analytics**: Memory effectiveness metrics
- **Debugging Tools**: Memory inspection capabilities
- **Scalable Architecture**: Session isolation

### For Evaluation:
- **Cross-Dataset Learning**: Patterns learned across BIRD variants
- **Performance Tracking**: Memory impact on accuracy
- **Failure Analysis**: Learn from errors
- **Continuous Improvement**: Accumulating knowledge

## 📊 Memory Management Strategy

### Session Isolation
- Each user session gets its own memory database
- `session_memory_{session_id}.db` naming convention
- Automatic cleanup of old sessions

### Memory Lifecycle
1. **Creation**: On first successful query
2. **Usage**: During similar query processing
3. **Update**: Performance tracking and refinement
4. **Consolidation**: Merge similar memories
5. **Cleanup**: Remove low-performing memories

### Performance Monitoring
- Memory hit rates per session
- Query improvement metrics
- Memory storage efficiency
- Cross-dataset transfer effectiveness

## 🚀 Implementation Priority

### High Priority (Immediate)
1. **API Stream Integration**: Real-time memory in query processing
2. **BIRD Evaluation**: Memory-enhanced evaluation accuracy
3. **Basic Web UI**: Memory visualization and management

### Medium Priority (Next Quarter)
1. **Cross-Dataset Learning**: Transfer learning between evaluations
2. **Advanced Analytics**: Memory performance insights
3. **Memory Export**: Sharing learned patterns

### Low Priority (Future)
1. **Multi-User Memory**: Shared organizational knowledge
2. **Memory Clustering**: Automatic pattern discovery
3. **External Memory**: Integration with external knowledge bases

## 🔐 Security Considerations

### Data Privacy
- Session-based memory isolation
- No cross-user memory sharing
- Automatic memory cleanup

### Memory Content Security
- Sanitize stored SQL patterns
- Prevent injection attacks via memory
- Audit memory access patterns

### Performance Security
- Memory size limits per session
- Rate limiting on memory operations
- Monitoring for memory abuse

This integration plan ensures the memory system becomes a core part of the SENS agent architecture, enhancing performance across all interfaces while maintaining security and scalability.
