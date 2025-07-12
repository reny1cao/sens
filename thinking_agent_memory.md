# Memory System for Thinking Agents

## 🧠 **Core Memory Integration Points**

### **1. Database Schema Memory**
When the agent explores a database, it should remember:

```python
# After successful EXPLORE_DATABASE action
await memory_tools.remember_concept(
    name=f"database_schema_{database_name}",
    description=f"Schema structure for {database_name}",
    business_terms=["tables", "columns", "relationships"],
    database_mapping={
        "database_path": database_path,
        "tables": discovered_tables,
        "table_schemas": table_definitions
    },
    context={
        "database_type": "sqlite",
        "exploration_date": datetime.now(),
        "table_count": len(discovered_tables)
    }
)
```

### **2. Query Pattern Memory**
When the agent successfully completes a query, store the pattern:

```python
# After successful query completion
await memory_tools.remember_pattern(
    name=f"query_pattern_{query_hash}",
    trigger_phrase=original_user_question,
    sql_template=final_sql,
    tables_used=tables_involved,
    success_context={
        "exploration_steps": exploration_actions,
        "reasoning_chain": reasoning_decisions,
        "iteration_count": final_iterations
    }
)
```

### **3. Reasoning Chain Memory**
Store successful reasoning chains:

```python
# After successful reasoning sequence
await memory_tools.remember_pattern(
    name=f"reasoning_chain_{problem_type}",
    trigger_phrase=problem_description,
    sql_template=reasoning_sequence,
    tables_used=["reasoning_steps"],
    success_context={
        "problem_type": "database_exploration",
        "steps_taken": step_sequence,
        "decision_points": key_decisions
    }
)
```

### **4. Error Recovery Memory**
When the agent recovers from errors:

```python
# After error recovery
await memory_tools.remember_error_fix(
    name=f"error_recovery_{error_type}",
    error_pattern=error_description,
    solution=recovery_actions,
    root_cause=error_analysis,
    context={
        "error_iteration": iteration_number,
        "recovery_steps": recovery_sequence
    }
)
```

## 🔧 **Implementation in Agent Core**

### **Enhanced Agent Action Execution**

```python
# In sens/agents/core.py
async def _execute_action(self, action: str, params: Dict = None):
    """Execute action with memory integration"""

    # 1. Check if we have relevant memory for this action
    if self.memory_enabled:
        relevant_memories = await self.memory_tools.recall_knowledge(
            query=f"{action} {self.current_query}",
            memory_types=["pattern", "concept"],
            context={"database": self.current_database},
            limit=3
        )

        # Apply memory insights to action
        if relevant_memories.success and relevant_memories.data["memories"]:
            self._apply_memory_insights(relevant_memories.data["memories"])

    # 2. Execute the action
    start_time = time.time()
    try:
        result = await self._perform_action(action, params)
        execution_time = time.time() - start_time

        # 3. Learn from successful action
        if result.get("success") and self.memory_enabled:
            await self._learn_from_action_success(action, params, result, execution_time)

        return result

    except Exception as e:
        execution_time = time.time() - start_time

        # 4. Learn from action failure
        if self.memory_enabled:
            await self._learn_from_action_failure(action, params, str(e), execution_time)

        raise e

async def _learn_from_action_success(self, action: str, params: Dict, result: Dict, execution_time: float):
    """Learn from successful action execution"""

    if action == "EXPLORE_DATABASE":
        # Remember database schema
        await self.memory_tools.remember_concept(
            name=f"db_schema_{result.get('database_path', 'unknown')}",
            description=f"Database schema exploration result",
            business_terms=["database", "tables", "schema"],
            database_mapping={
                "database_path": result.get("database_path"),
                "tables": result.get("tables", []),
                "table_count": result.get("table_count", 0)
            },
            context={
                "action": action,
                "execution_time": execution_time,
                "iteration": self.current_iteration
            }
        )

        # If this solved our exploration need, remember the pattern
        if self._exploration_successful(result):
            await self.memory_tools.remember_pattern(
                name=f"db_exploration_pattern_{hash(self.current_query)}",
                trigger_phrase=self.current_query,
                sql_template=f"EXPLORE_DATABASE -> {action}",
                tables_used=result.get("tables", []),
                success_context={
                    "exploration_result": result,
                    "iteration": self.current_iteration,
                    "reasoning": self.current_reasoning
                }
            )

    elif action == "EXECUTE_SQL":
        # Remember successful SQL execution
        await self.memory_tools.remember_pattern(
            name=f"sql_execution_{hash(params.get('sql', ''))}",
            trigger_phrase=self.current_query,
            sql_template=params.get("sql", ""),
            tables_used=self._extract_tables_from_sql(params.get("sql", "")),
            success_context={
                "result": result,
                "row_count": result.get("row_count", 0),
                "execution_time": execution_time
            }
        )

        # Connect to related database schema memory
        schema_memories = await self.memory_tools.recall_knowledge(
            query=f"db_schema_{result.get('database_path', 'unknown')}",
            memory_types=["concept"],
            limit=1
        )

        if schema_memories.success and schema_memories.data["memories"]:
            schema_memory = schema_memories.data["memories"][0]
            current_pattern_id = await self._get_current_pattern_id()

            if current_pattern_id:
                await self.memory_tools.connect_memories(
                    from_memory_id=current_pattern_id,
                    to_memory_id=schema_memory["id"],
                    relationship_type="uses_schema",
                    strength=0.8,
                    reason="SQL pattern uses database schema"
                )

async def _apply_memory_insights(self, memories: List[Dict]):
    """Apply memory insights to current reasoning"""

    memory_insights = []

    for memory in memories:
        if memory["type"] == "concept" and "database_mapping" in memory["content"]:
            # Add database schema insights
            schema_info = memory["content"]["database_mapping"]
            memory_insights.append(f"Database has {len(schema_info.get('tables', []))} tables: {schema_info.get('tables', [])}")

        elif memory["type"] == "pattern" and "sql_template" in memory["content"]:
            # Add SQL pattern insights
            pattern_info = memory["content"]
            memory_insights.append(f"Similar query pattern: {pattern_info.get('trigger_phrase', 'unknown')}")
            memory_insights.append(f"Used tables: {pattern_info.get('tables_used', [])}")
            memory_insights.append(f"SQL template: {pattern_info.get('sql_template', 'unknown')}")

    # Add memory insights to agent notes
    if memory_insights:
        memory_context = "MEMORY INSIGHTS:\n" + "\n".join(f"- {insight}" for insight in memory_insights)
        self.add_note(memory_context)

        # Log memory application
        log.info("memory_insights_applied",
                insights_count=len(memory_insights),
                memory_count=len(memories),
                iteration=self.current_iteration)
```

### **Memory-Enhanced Reasoning**

```python
# In sens/agents/reasoning.py
async def reason_with_memory(self, query: str, context: Dict, memory_tools: AgentMemoryTools = None):
    """Enhanced reasoning with memory integration"""

    reasoning_context = context.copy()

    # Add memory context if available
    if memory_tools:
        # Recall relevant reasoning patterns
        reasoning_memories = await memory_tools.recall_knowledge(
            query=f"reasoning {query}",
            memory_types=["pattern"],
            context={"reasoning": True},
            limit=3
        )

        if reasoning_memories.success and reasoning_memories.data["memories"]:
            memory_patterns = []
            for memory in reasoning_memories.data["memories"]:
                if "reasoning_chain" in memory["content"]:
                    memory_patterns.append(memory["content"]["reasoning_chain"])

            if memory_patterns:
                reasoning_context["memory_patterns"] = memory_patterns
                reasoning_context["memory_guidance"] = "Use previous successful reasoning patterns as guidance"

    # Perform reasoning with memory context
    reasoning_result = await self._perform_reasoning(query, reasoning_context)

    # Learn from reasoning if successful
    if reasoning_result.get("success") and memory_tools:
        await self._learn_from_reasoning(query, reasoning_result, memory_tools)

    return reasoning_result

async def _learn_from_reasoning(self, query: str, reasoning_result: Dict, memory_tools: AgentMemoryTools):
    """Learn from successful reasoning"""

    await memory_tools.remember_pattern(
        name=f"reasoning_pattern_{hash(query)}",
        trigger_phrase=query,
        sql_template=reasoning_result.get("reasoning_chain", ""),
        tables_used=["reasoning"],
        success_context={
            "reasoning_steps": reasoning_result.get("steps", []),
            "decision_points": reasoning_result.get("decisions", []),
            "success_factors": reasoning_result.get("success_factors", [])
        },
        context={"reasoning": True, "pattern_type": "reasoning_chain"}
    )
```

## 🎯 **Memory Application in Your Example**

### **What Would Happen in Your Case:**

1. **First Database Exploration** (Iteration 2):
   ```
   Action: EXPLORE_DATABASE
   Result: Found 3 tables (frpm, schools, satscores)
   Memory: Store database schema concept
   ```

2. **Second Database Exploration** (Iteration 3):
   ```
   Memory Recall: "I've already explored this database"
   Memory Insight: "Database has frpm table with columns: CDSCode, Academic Year, County Code..."
   Agent Decision: "I already know the schema, let me look for specific columns"
   ```

3. **Third Database Exploration** (Iteration 4):
   ```
   Memory Recall: "I've explored frpm table twice"
   Memory Insight: "frpm table doesn't have charter/phone info, try schools table"
   Agent Decision: "Switch to schools table based on memory"
   ```

### **Memory-Enhanced Agent Logs:**

```
🧠 Memory Recall: Found database schema for california_schools.sqlite
🧠 Memory Insight: Database has 3 tables: frpm, schools, satscores
🔧 Action: EXPLORE_DATABASE (table_name=schools)
   Reason: Memory indicates schools table likely contains charter and phone info
👁️ Observation: ✅ Success - Found charter and phone columns in schools table
🧠 Memory Learning: Stored successful exploration pattern
```

## 📊 **Memory Benefits for Thinking Agents**

1. **Reduced Iterations**: Skip redundant explorations
2. **Smarter Decisions**: Use previous successful patterns
3. **Error Avoidance**: Remember what doesn't work
4. **Context Preservation**: Maintain knowledge across sessions
5. **Progressive Learning**: Get better over time

## 🔧 **Implementation Priority**

1. **Database Schema Memory** (High Priority)
2. **Query Pattern Memory** (High Priority)
3. **Reasoning Chain Memory** (Medium Priority)
4. **Error Recovery Memory** (Medium Priority)
5. **Cross-Session Learning** (Low Priority)

This memory system would transform your thinking agent from repeating the same explorations to building on previous knowledge, making it much more efficient and intelligent over time!
