# SENS Agent Architecture Refactoring Plan

## 🎯 Goal
Consolidate 6+ agent implementations into a single, clean, unified architecture while maintaining web UI streaming capabilities.

## 🏗️ New Architecture

### Core Components (Keep & Enhance)
```
src/sens/agents/
├── unified.py              # NEW: Single agent implementation
├── base.py                 # Keep: Base interfaces
├── reasoning.py            # Keep: Reasoning engine
├── reflection.py           # Keep: Reflection engine
├── tools.py                # Keep: Agent tools
└── answer_generator.py     # Keep: Answer generation
```

### API Layer (Simplified)
```
src/sens/api/routers/
├── agent_stream_unified.py # NEW: Unified streaming endpoint
├── nl2sql_unified.py       # Keep: Core NL2SQL
└── [other routers]         # Keep: Supporting functionality
```

## 🗑️ Components to Remove

### Redundant Agent Implementations
1. **event_emitter.py** - Functionality merged into unified.py
2. **core.py** - Base functionality merged into unified.py
3. **memory_layered_agent.py** - Memory features integrated into unified.py
4. **memory_enhanced_core.py** - Memory features integrated into unified.py
5. **langgraph_agent.py** - Experimental, not in production use
6. **event_emitting_langgraph.py** - Duplicate of langgraph with events

### Redundant API Endpoints
1. **agent_stream.py** - Replaced by agent_stream_unified.py
2. **agent_stream_enhanced.py** - Replaced by agent_stream_unified.py
3. **archived/nl2sql_agent.py** - Already archived
4. **archived/nl2sql_simple_agent.py** - Already archived

### Redundant Pipelines
1. **pipeline/agent.py** - Stub implementation, not used
2. Multiple pipeline wrappers with duplicate logic

## 📋 Migration Steps

### Phase 1: Create Unified Implementation ✅
- [x] Create UnifiedSENSAgent with all features
- [x] Create unified streaming endpoint
- [x] Create unified app configuration

### Phase 2: Update Web UI Integration
```javascript
// Update frontend to use new endpoint
const API_ENDPOINT = '/api/nl2sql/agent/stream';  // Unified endpoint
```

### Phase 3: Update CLI Integration
```python
# In agent_pipeline.py
from sens.agents.unified import UnifiedSENSAgent

# Replace EventEmittingAgent with UnifiedSENSAgent
self.agent = UnifiedSENSAgent(
    tools=self.agent_tools,
    memory_tools=self.memory_tools,
    reasoning_engine=self.reasoning_engine,
    max_iterations=max_iterations,
    streaming_enabled=True,  # For CLI progress
    memory_enabled=True,
    reflection_enabled=True
)
```

### Phase 4: Remove Deprecated Code
```bash
# After verification, remove deprecated files
rm src/sens/agents/event_emitter.py
rm src/sens/agents/core.py
rm src/sens/agents/memory_layered_agent.py
rm src/sens/agents/memory_enhanced_core.py
rm src/sens/agents/langgraph_agent.py
rm src/sens/agents/event_emitting_langgraph.py
rm src/sens/api/routers/agent_stream.py
rm src/sens/api/routers/agent_stream_enhanced.py
rm -rf src/sens/api/routers/archived/
```

## 🔍 Testing Strategy

### Unit Tests
```python
# Test unified agent
def test_unified_agent_streaming():
    agent = UnifiedSENSAgent(streaming_enabled=True)
    # Test streaming functionality

def test_unified_agent_memory():
    agent = UnifiedSENSAgent(memory_enabled=True)
    # Test memory integration

def test_unified_agent_minimal_mode():
    agent = UnifiedSENSAgent(minimal_mode=True)
    # Test performance mode
```

### Integration Tests
1. Web UI streaming with new endpoint
2. CLI functionality with unified agent
3. Memory persistence across sessions
4. Performance benchmarks

## 📊 Expected Benefits

### Code Reduction
- **60% less code** in agent implementations
- **Single source of truth** for agent behavior
- **Unified memory integration** pattern

### Performance Improvements
- **Consistent caching** across all interfaces
- **Non-blocking memory operations** everywhere
- **Reduced object creation** overhead

### Maintainability
- **Single place** to add new features
- **Consistent error handling**
- **Unified logging and metrics**

### Developer Experience
- **Clear architecture** without redundancy
- **Easy to understand** codebase
- **Consistent patterns** throughout

## 🚀 Rollout Plan

### Week 1: Development & Testing
- Implement unified components
- Update unit tests
- Internal testing

### Week 2: Staging Deployment
- Deploy to staging environment
- Web UI integration testing
- Performance benchmarking

### Week 3: Production Rollout
- Gradual rollout with feature flags
- Monitor metrics and errors
- Full deployment

### Week 4: Cleanup
- Remove deprecated code
- Update documentation
- Archive old implementations

## 🎯 Success Metrics

1. **No regression** in web UI functionality
2. **Improved response times** (target: 10% faster)
3. **Reduced memory usage** (target: 20% less)
4. **Cleaner codebase** (60% less agent code)
5. **Better test coverage** (target: 90%+)

## 🔒 Rollback Plan

If issues arise:
1. Feature flag to use old implementation
2. Keep deprecated code for 30 days
3. Quick revert capability via git

## 📝 Documentation Updates

1. Update API documentation
2. Update architecture diagrams
3. Update developer guide
4. Create migration guide for plugins/extensions
