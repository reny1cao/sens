# Unified BIRD Evaluation System

This document explains how to use the new unified evaluation system that supports multiple BIRD datasets with different evaluation criteria.

## Supported Datasets

### 1. BIRD-CRITIC (SQL Debugging)
- **Dataset**: `birdsql/bird-critic-1.0-postgresql` from Hugging Face
- **Evaluation**: Execution-based (no golden SQL comparison)
- **Focus**: SQL debugging and fixing
- **Metrics**: Execution success rate, error breakdown
- **Database**: Requires BIRD-CRITIC PostgreSQL databases

### 2. BIRD-SQL-DEV (Text-to-SQL)
- **Dataset**: Local JSON file (`external/BIRD-SQL-DEV/dev.json`)
- **Evaluation**: Both execution-based AND golden SQL comparison
- **Focus**: Traditional text-to-SQL generation
- **Metrics**: Execution success, SQL match rates, exact match rates
- **Database**: Requires BIRD-SQL-DEV databases (california_schools, etc.)

## Dataset Comparison

| Feature | BIRD-CRITIC | BIRD-SQL-DEV |
|---------|-------------|--------------|
| **Purpose** | SQL debugging/fixing | Text-to-SQL generation |
| **Golden SQL** | ❌ No | ✅ Yes |
| **Evaluation** | Execution only | Execution + SQL comparison |
| **Task Count** | 530 | 1,534 |
| **Difficulty Levels** | No | Yes (simple, moderate, challenging) |
| **Evidence Field** | No | Yes |

## CLI Usage

### Basic Commands

```bash
# Show help
poetry run sens unified-bird --help

# Run evaluation on both datasets
poetry run sens unified-bird run \
  --bird-critic \
  --bird-sql-dev external/BIRD-SQL-DEV/dev.json \
  --limit 10 \
  --output results.json

# Run only BIRD-CRITIC evaluation
poetry run sens unified-bird run \
  --bird-critic \
  --limit 5 \
  --output bird_critic_results.json

# Run only BIRD-SQL-DEV evaluation
poetry run sens unified-bird run \
  --bird-sql-dev external/BIRD-SQL-DEV/dev.json \
  --limit 5 \
  --output bird_sql_dev_results.json

# Analyze results
poetry run sens unified-bird analyze results.json
```

### Advanced Options

```bash
# Enable debug logging
poetry run sens unified-bird run \
  --bird-sql-dev external/BIRD-SQL-DEV/dev.json \
  --debug \
  --limit 3

# Custom database prefix
poetry run sens unified-bird run \
  --bird-critic \
  --database-prefix "my_bird_" \
  --limit 5
```

## API Usage

### Start Unified Evaluation

```http
POST /api/evaluation/unified-bird/start
Content-Type: application/json

{
  "include_bird_critic": true,
  "bird_sql_dev_path": "external/BIRD-SQL-DEV/dev.json",
  "limit": 10,
  "database_prefix": "bird_",
  "debug_mode": true,
  "max_iterations": 25
}
```

### Stream Evaluation Progress

```http
GET /api/evaluation/unified-bird/stream/{evaluation_id}
Accept: text/event-stream
```

### Get Evaluation Status

```http
GET /api/evaluation/unified-bird/status/{evaluation_id}
```

## Output Formats

### Unified Results JSON

```json
[
  {
    "task_id": "0",
    "db_id": "california_schools",
    "question": "What is the highest eligible free rate...",
    "dataset_type": "bird_sql_dev",
    "generated_sql": "SELECT MAX(free_rate) FROM schools...",
    "execution_success": true,
    "execution_error": null,
    "result_count": 1,
    "execution_time_ms": 45.2,
    "difficulty": "simple",
    "golden_sql": "SELECT MAX(eligible_free_rate) FROM...",
    "sql_match": false,
    "sql_equivalence": false
  }
]
```

### Unified Metrics JSON

```json
{
  "total_tasks": 20,
  "bird_critic_tasks": 10,
  "bird_sql_dev_tasks": 10,
  "overall_execution_success_rate": 0.75,
  "bird_critic_execution_success_rate": 0.8,
  "bird_sql_dev_execution_success_rate": 0.7,
  "bird_sql_dev_sql_match_rate": 0.6,
  "bird_sql_dev_exact_match_rate": 0.4,
  "avg_execution_time_ms": 125.3
}
```

## Database Setup Requirements

### BIRD-CRITIC Databases
- PostgreSQL databases with `bird_` prefix
- Schema file: `external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl`
- Example databases: `bird_financial`, `bird_codebase_community`

### BIRD-SQL-DEV Databases
- PostgreSQL databases matching `db_id` field
- Example databases: `california_schools`, `college_2`, `concert_singer`
- Database dumps available in `external/BIRD-SQL-DEV/dev_databases/`

## Key Features

### 1. SQL Comparison (BIRD-SQL-DEV only)
- **Exact Match**: Character-by-character comparison
- **Normalized Match**: Case-insensitive, whitespace-normalized comparison
- **Execution Comparison**: Both SQLs run successfully

### 2. Unified Metrics
- **Dataset-specific metrics**: Separate success rates per dataset type
- **Combined metrics**: Overall success rate across all tasks
- **Performance metrics**: Execution times, error breakdowns

### 3. Real-time Streaming
- **SSE Support**: Real-time progress updates
- **Event Types**: task_start, task_complete, metrics_update, evaluation_complete
- **Agent Events**: For BIRD-CRITIC tasks, includes agent reasoning steps

### 4. Flexible Configuration
- **Dataset Selection**: Choose which datasets to include
- **Task Limiting**: Evaluate subset of tasks for testing
- **Debug Mode**: Verbose logging and agent trace capture

## Error Handling

### Common Issues

1. **Database Connection Failures**
   ```bash
   Error: Failed to connect to database bird_california_schools
   ```
   **Solution**: Ensure BIRD-SQL-DEV databases are set up

2. **File Not Found**
   ```bash
   Error: File not found: external/BIRD-SQL-DEV/dev.json
   ```
   **Solution**: Check file path and ensure BIRD-SQL-DEV is downloaded

3. **Agent Pipeline Errors**
   ```bash
   Error: 'dict' object has no attribute 'final_result'
   ```
   **Solution**: This has been fixed in the latest version

### Debug Tips

1. **Enable Debug Mode**: Use `--debug` flag for verbose logging
2. **Start Small**: Use `--limit 1` to test single task
3. **Check Databases**: Verify database connections before large evaluations
4. **Monitor Resources**: Large evaluations can be memory/time intensive

## Integration with Web Interface

The unified evaluation system can be integrated with the existing web interface by:

1. **Adding Dataset Selection**: UI to choose BIRD-CRITIC vs BIRD-SQL-DEV
2. **Enhanced Metrics Display**: Show dataset-specific success rates
3. **SQL Comparison View**: For BIRD-SQL-DEV, show generated vs golden SQL
4. **Difficulty Breakdown**: Show performance by difficulty level

## Future Enhancements

1. **Additional Datasets**: Support for more BIRD variants
2. **Semantic SQL Comparison**: Beyond text matching
3. **Cross-dataset Analysis**: Compare performance across dataset types
4. **Batch Evaluation**: Parallel task execution
5. **Result Caching**: Cache evaluation results for analysis

## Development

### Adding New Dataset Types

1. **Define DatasetType**: Add to `DatasetType` enum
2. **Create Task Loader**: Add loader method to `UnifiedBirdEvaluator`
3. **Implement Evaluator**: Add evaluation logic for new dataset type
4. **Update Metrics**: Add dataset-specific metrics calculation
5. **Update CLI/API**: Add options for new dataset type

### Testing

```bash
# Run simple structure test
poetry run python test_unified_simple.py

# Test CLI commands
poetry run sens unified-bird run --help
```
