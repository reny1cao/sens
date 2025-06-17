# ReAct Reflection Enhancement Implementation Plan

## Overview
Enhance the Reflect phase in the ReAct loop to interpret results, extract learnings, and maintain agent notes for better decision-making.

## Current State Analysis

### Problem
The agent gets stuck in loops because it doesn't learn from observations:
- Explores same table repeatedly
- Doesn't note what columns are missing
- Doesn't remember failed approaches
- Can't build on previous discoveries

### Root Cause
The `reflect()` method is minimal - it only checks success/failure without interpreting what was learned.

## Proposed Solution

### 1. Enhanced Reflect Method Structure

```python
async def reflect(self, state: AgentState, observation: AgentObservation) -> None:
    """Reflect on observation to extract learnings and update notes."""

    # 1. Interpret the observation based on action type
    interpretation = await self._interpret_observation(
        state.get_last_action(),
        observation
    )

    # 2. Extract key learnings
    learnings = self._extract_learnings(
        action=state.get_last_action(),
        observation=observation,
        interpretation=interpretation
    )

    # 3. Update agent notes with learnings
    if learnings:
        notes_update = self._format_learnings_as_notes(learnings)
        state.update_notes(notes_update)

    # 4. Update discovered mappings if applicable
    self._update_mappings(state, learnings)

    # 5. Check for patterns (repeated failures, stuck loops)
    patterns = self._detect_patterns(state)
    if patterns:
        state.update_notes(f"Pattern detected: {patterns}")
```

### 2. Interpretation Logic

```python
async def _interpret_observation(self, action: AgentAction, observation: AgentObservation) -> Dict[str, Any]:
    """Interpret what the observation means in context of the action."""

    interpretation = {
        "what_found": [],
        "what_missing": [],
        "implications": [],
        "next_steps": []
    }

    if action.action_type == ActionType.EXPLORE_DATABASE:
        if "columns" in observation.content:
            # Analyzing table structure exploration
            columns = observation.content.get("columns", [])

            # What we found
            interpretation["what_found"] = columns

            # What's missing (based on user query needs)
            needed_columns = self._identify_needed_columns(state.user_query)
            interpretation["what_missing"] = [
                col for col in needed_columns
                if col not in columns
            ]

            # Implications
            if interpretation["what_missing"]:
                interpretation["implications"].append(
                    f"This table lacks {', '.join(interpretation['what_missing'])}"
                )
                interpretation["next_steps"].append(
                    "Need to find another table with this information"
                )

    return interpretation
```

### 3. Learning Extraction

```python
def _extract_learnings(self, action: AgentAction, observation: AgentObservation, interpretation: Dict) -> Dict[str, Any]:
    """Extract concrete learnings from the observation."""

    learnings = {
        "facts": [],      # Concrete facts discovered
        "rules": [],      # Rules/patterns learned
        "mappings": {},   # Value mappings discovered
        "exclusions": []  # What to avoid trying again
    }

    # Example: Learning from table exploration
    if action.action_type == ActionType.EXPLORE_DATABASE:
        query = action.parameters.get("query", "")

        # Extract table name from query
        if "FROM" in query:
            table_name = self._extract_table_from_query(query)

            if interpretation["what_missing"]:
                learnings["facts"].append(
                    f"Table '{table_name}' does not contain columns: {', '.join(interpretation['what_missing'])}"
                )
                learnings["exclusions"].append(
                    f"Don't look for {interpretation['what_missing']} in {table_name}"
                )

            if interpretation["what_found"]:
                learnings["facts"].append(
                    f"Table '{table_name}' contains columns: {', '.join(interpretation['what_found'][:5])}"
                )

    # Example: Learning from value discovery
    elif action.action_type == ActionType.EXPLORE_DATABASE and "symbol" in str(observation.content):
        # Extract symbol mappings
        if isinstance(observation.content.get("data"), list):
            for row in observation.content["data"]:
                if "symbol" in row and "company_name" in row:
                    learnings["mappings"][row["company_name"]] = row["symbol"]

    return learnings
```

### 4. Pattern Detection

```python
def _detect_patterns(self, state: AgentState) -> Optional[str]:
    """Detect problematic patterns in agent behavior."""

    # Check for repeated actions
    recent_actions = state.actions[-5:]
    if len(recent_actions) >= 3:
        # Check if exploring same table repeatedly
        queries = [
            a.parameters.get("query", "")
            for a in recent_actions
            if a.action_type == ActionType.EXPLORE_DATABASE
        ]

        tables = [self._extract_table_from_query(q) for q in queries]
        if tables.count(tables[0]) >= 3:
            return f"Stuck exploring '{tables[0]}' table repeatedly"

    # Check for no progress
    if state.iteration > 3 and not state.current_sql:
        return "No SQL generated after multiple iterations"

    return None
```

### 5. Notes Formatting

```python
def _format_learnings_as_notes(self, learnings: Dict[str, Any]) -> str:
    """Format learnings into readable notes."""

    notes_parts = []

    # Add facts
    if learnings["facts"]:
        notes_parts.append("Discovered: " + "; ".join(learnings["facts"]))

    # Add mappings
    if learnings["mappings"]:
        mapping_str = ", ".join([f"{k}→{v}" for k, v in learnings["mappings"].items()])
        notes_parts.append(f"Value mappings: {mapping_str}")

    # Add exclusions
    if learnings["exclusions"]:
        notes_parts.append("Avoid: " + "; ".join(learnings["exclusions"]))

    return " | ".join(notes_parts)
```

## Implementation Steps

### Step 1: Create Reflection Module (Week 1)
- [ ] Create `sens/agents/reflection.py` with interpretation logic
- [ ] Implement observation interpreters for each action type
- [ ] Add learning extraction methods
- [ ] Create pattern detection algorithms

### Step 2: Integrate with Core Agent (Week 1)
- [ ] Update `reflect()` method in `SENSAgent`
- [ ] Ensure notes are updated after each observation
- [ ] Add reflection context to reasoning

### Step 3: Enhance Context Building (Week 2)
- [ ] Update `get_recent_context()` to include interpretations
- [ ] Add notes summary to context
- [ ] Include learned exclusions

### Step 4: Test and Refine (Week 2)
- [ ] Create test cases for stuck scenarios
- [ ] Verify notes capture negative findings
- [ ] Ensure agent breaks out of loops

## Example Flow

```
User: "Show me tech stocks by market cap"

Iteration 1:
- Reason: Need to explore database structure
- Act: EXPLORE_DATABASE (list tables)
- Observe: Found daily_prices, securities, fundamentals tables
- Reflect: "Discovered: Database has tables for prices, company info, and fundamentals"

Iteration 2:
- Reason: Need to check daily_prices for market cap (notes show tables exist)
- Act: EXPLORE_DATABASE (daily_prices columns)
- Observe: symbol, price, volume (no market_cap)
- Reflect: "Discovered: daily_prices lacks market_cap column; Avoid: looking for market_cap in daily_prices"

Iteration 3:
- Reason: Check fundamentals table since daily_prices lacks market_cap (notes show exclusion)
- Act: EXPLORE_DATABASE (fundamentals columns)
- Observe: symbol, market_cap, pe_ratio, sector
- Reflect: "Discovered: fundamentals table has market_cap and sector data"

Iteration 4:
- Reason: Have all needed info (notes show where each piece of data lives)
- Act: GENERATE_SQL (join daily_prices and fundamentals)
- Success!
```

## Benefits

1. **No More Loops**: Agent remembers what doesn't work
2. **Faster Discovery**: Builds on previous learnings
3. **Better Decisions**: Uses accumulated knowledge
4. **Clear Progress**: Notes show what's been learned
5. **Smarter Exploration**: Avoids repeated failures

## Success Metrics

- Agent escapes exploration loops within 2 iterations
- Notes capture both positive and negative findings
- Complex queries succeed in fewer iterations
- Agent can explain its reasoning path clearly
