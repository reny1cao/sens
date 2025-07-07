# BIRD-SQL-DEV Evaluation System

This document explains the separate BIRD-SQL-DEV evaluation system for text-to-SQL generation using SQLite databases with golden SQL comparison.

## Overview

The BIRD-SQL-DEV evaluation system is designed specifically for traditional text-to-SQL evaluation tasks:

- **Dataset**: Local JSON file (`external/BIRD-SQL-DEV/dev.json`)
- **Database**: SQLite databases (not PostgreSQL)
- **Evaluation**: Both execution-based AND golden SQL comparison
- **Focus**: Traditional text-to-SQL generation with accuracy metrics
- **Golden SQL**: Available for exact match and normalized match comparison
- **Execution Equivalence**: Compares actual query results

## Key Differences from BIRD-CRITIC

| Feature | BIRD-CRITIC | BIRD-SQL-DEV |
|---------|-------------|---------------|
| **Purpose** | SQL debugging/fixing | Text-to-SQL generation |
| **Database** | PostgreSQL with `bird_` prefix | SQLite files |
| **Golden SQL** | ❌ No | ✅ Yes |
| **Evaluation** | Execution only | Execution + SQL comparison + Result comparison |
| **Use Case** | Fixing broken SQL | Generating SQL from natural language |

## Setup Requirements

### 1. Dataset File
Place the BIRD-SQL-DEV dataset at:
```
external/BIRD-SQL-DEV/dev.json
```

### 2. SQLite Databases
Place SQLite database files in:
```
external/BIRD-SQL-DEV/dev_databases/
```

Database files should be named: `{db_id}.sqlite`, `{db_id}.db`, or `{db_id}.sqlite3`

Example structure:
```
external/BIRD-SQL-DEV/
├── dev.json
└── dev_databases/
    ├── california_schools.sqlite
    ├── college_2.sqlite
    ├── concert_singer.sqlite
    └── ...
```

## CLI Usage

### Basic Commands

```bash
# Show help
poetry run sens bird-sql-dev --help

# Run evaluation on all tasks
poetry run sens bird-sql-dev run \
  --dataset external/BIRD-SQL-DEV/dev.json \
  --output bird_sql_dev_results.json

# Run limited evaluation for testing
poetry run sens bird-sql-dev run \
  --dataset external/BIRD-SQL-DEV/dev.json \
  --limit 10 \
  --output test_results.json

# Enable debug mode
poetry run sens bird-sql-dev run \
  --dataset external/BIRD-SQL-DEV/dev.json \
  --limit 5 \
  --debug \
  --output debug_results.json

# Custom database directory
poetry run sens bird-sql-dev run \
  --dataset external/BIRD-SQL-DEV/dev.json \
  --database-dir /path/to/sqlite/files \
  --limit 5
```

### Analysis Commands

```bash
# Analyze results
poetry run sens bird-sql-dev analyze bird_sql_dev_results.json

# Check setup status
poetry run sens bird-sql-dev status
poetry run sens bird-sql-dev status --database-dir /custom/path
```

### Example Output

```bash
🐦 Starting BIRD-SQL-DEV Evaluation
========================================
📥 Loading tasks from external/BIRD-SQL-DEV/dev.json
📊 Loaded 1534 tasks, evaluating 10
⚠️  Limiting evaluation to first 10 tasks for testing
🔍 Checking database availability...
✅ Database check passed (5/5 checked)

🚀 Starting evaluation of 10 tasks...
Evaluating tasks  [####################################]  100%

🎯 BIRD-SQL-DEV Evaluation Results
========================================
Total tasks: 10
Execution success rate: 70.0%
Exact match rate: 40.0%
Normalized match rate: 50.0%
Execution match rate: 60.0%
Average execution time: 234.5ms

📈 Performance by Difficulty:
  Simple: 80.0% success, 60.0% exact match (5 tasks)
  Moderate: 66.7% success, 33.3% exact match (3 tasks)
  Challenging: 50.0% success, 0.0% exact match (2 tasks)

💾 Saving results to bird_sql_dev_results.json
✅ Results saved!
📊 Metrics saved to bird_sql_dev_results_metrics.json

🎉 BIRD-SQL-DEV evaluation completed!
```

## API Usage

### Start Evaluation

```http
POST /api/evaluation/bird-sql-dev/start
Content-Type: application/json

{
  "dataset_path": "external/BIRD-SQL-DEV/dev.json",
  "database_dir": "external/BIRD-SQL-DEV/dev_databases",
  "limit": 10,
  "debug_mode": true,
  "max_iterations": 25
}
```

Response:
```json
{
  "evaluation_id": "abc123...",
  "status": "running",
  "total_tasks": 10,
  "completed_tasks": 0,
  "successful_tasks": 0,
  "failed_tasks": 0,
  "start_time": "2024-01-15T10:30:00Z"
}
```

### Stream Progress

```http
GET /api/evaluation/bird-sql-dev/stream/{evaluation_id}
Accept: text/event-stream
```

Real-time events:
- `evaluation_start`: Evaluation begins
- `task_start`: New task starts
- `thinking`: Agent reasoning steps
- `action`: Agent actions
- `observation`: Action results
- `sql_generated`: SQL query generated
- `task_complete`: Task finished with results
- `metrics_update`: Updated metrics
- `evaluation_complete`: All tasks finished

### Get Status

```http
GET /api/evaluation/bird-sql-dev/status/{evaluation_id}
```

## Evaluation Metrics

### Core Metrics

1. **Execution Success Rate**: Percentage of tasks where generated SQL executes without errors
2. **Exact Match Rate**: Percentage of tasks where generated SQL exactly matches golden SQL
3. **Normalized Match Rate**: Percentage of tasks where generated SQL matches after normalization
4. **Execution Match Rate**: Percentage of tasks where generated and golden SQL produce identical results

### Additional Metrics

- **Performance by Difficulty**: Success rates broken down by task difficulty
- **Database Performance**: Success rates by database
- **Error Analysis**: Breakdown of error types
- **Execution Time**: Average query execution time

### Sample Metrics Output

```json
{
  "total_tasks": 100,
  "execution_success_rate": 0.75,
  "exact_match_rate": 0.45,
  "normalized_match_rate": 0.52,
  "execution_match_rate": 0.68,
  "avg_execution_time_ms": 187.3,
  "difficulty_breakdown": {
    "simple": {
      "total": 40,
      "success": 32,
      "exact_match": 25,
      "success_rate": 0.80,
      "exact_match_rate": 0.625
    },
    "moderate": {
      "total": 35,
      "success": 24,
      "exact_match": 12,
      "success_rate": 0.686,
      "exact_match_rate": 0.343
    },
    "challenging": {
      "total": 25,
      "success": 19,
      "exact_match": 8,
      "success_rate": 0.76,
      "exact_match_rate": 0.32
    }
  }
}
```

## Result Format

### Individual Task Result

```json
{
  "question_id": "123",
  "db_id": "california_schools",
  "question": "What is the highest eligible free rate for K-12 students?",
  "generated_sql": "SELECT MAX(free_rate) FROM schools WHERE type = 'K-12'",
  "golden_sql": "SELECT MAX(eligible_free_rate) FROM frpm WHERE grade_level = 'K-12'",
  "execution_success": true,
  "execution_error": null,
  "result_count": 1,
  "execution_time_ms": 45.2,
  "exact_match": false,
  "normalized_match": false,
  "execution_match": false,
  "difficulty": "simple",
  "evidence": "Free rate refers to percentage of students eligible for free meals"
}
```

## Error Handling

### Common Issues

1. **Database File Not Found**
   ```
   Database file not found: /path/to/california_schools.sqlite
   ```
   **Solution**: Ensure SQLite files exist with correct naming convention

2. **Dataset File Missing**
   ```
   Dataset file not found: external/BIRD-SQL-DEV/dev.json
   ```
   **Solution**: Download and place the BIRD-SQL-DEV dataset correctly

3. **SQLite Connection Error**
   ```
   no such table: frpm
   ```
   **Solution**: Verify database schema matches expected tables

4. **SQL Generation Failure**
   ```
   SQL generation failed: Unable to map user terms to database values
   ```
   **Solution**: This indicates the agent couldn't generate valid SQL

### Debug Mode

Enable debug mode for detailed logging:

```bash
poetry run sens bird-sql-dev run \
  --dataset external/BIRD-SQL-DEV/dev.json \
  --limit 1 \
  --debug
```

Debug output includes:
- Detailed task information
- Agent thinking steps
- SQL generation process
- Execution details
- Error stack traces

## Integration with Web Interface

The BIRD-SQL-DEV evaluation system can be integrated with the web interface:

1. **Dataset Selection**: Separate tab for BIRD-SQL-DEV evaluation
2. **Real-time Streaming**: Shows agent thinking steps like BIRD-CRITIC
3. **SQL Comparison View**: Side-by-side view of generated vs golden SQL
4. **Metrics Dashboard**: BIRD-SQL-DEV specific metrics display
5. **Difficulty Analysis**: Performance breakdown by difficulty level

## Development

### Testing

```bash
# Run simple structure test
poetry run python test_bird_sql_dev_simple.py

# Test with actual dataset (if available)
poetry run sens bird-sql-dev run \
  --dataset external/BIRD-SQL-DEV/dev.json \
  --limit 1 \
  --debug
```

### Adding New Features

1. **Custom SQL Comparison**: Extend `_compare_sql` method
2. **Additional Metrics**: Update `calculate_metrics` method
3. **New Database Support**: Modify `_get_database_path` for other formats
4. **Enhanced Streaming**: Add new event types to `_transform_agent_event_for_bird_sql_dev`

## Performance Considerations

- **SQLite Performance**: Generally faster than PostgreSQL for read-only operations
- **Parallel Evaluation**: Tasks are evaluated sequentially (consider parallelization for production)
- **Memory Usage**: Results are stored in memory during evaluation
- **File I/O**: SQLite files are accessed for each task (consider connection pooling)

## Future Enhancements

1. **Semantic SQL Comparison**: Beyond text matching using AST comparison
2. **Execution Plan Analysis**: Compare query execution plans
3. **Schema-aware Evaluation**: Consider database schema in evaluation
4. **Batch Processing**: Parallel task evaluation
5. **Result Caching**: Cache evaluation results for analysis
