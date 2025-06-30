# BIRD-CRITIC Evaluation Setup

This document describes how to set up and run BIRD-CRITIC evaluations for the SENS system.

## Overview

BIRD-CRITIC is a benchmark dataset for evaluating text-to-SQL systems on real-world, buggy SQL queries from StackOverflow. It provides:

- 530 evaluation tasks with natural language questions
- Buggy SQL queries that need to be fixed
- Ground truth SQL solutions
- PostgreSQL database dumps for testing

## Setup Instructions

### 1. Install Dependencies

The evaluation system requires the `datasets` package for Hugging Face integration:

```bash
poetry add datasets
```

### 2. Clone BIRD-CRITIC Repository

The evaluation system automatically clones the BIRD-CRITIC repository to get schema files and database dumps:

```bash
# This is done automatically when you run the setup command
poetry run sens bird-critic setup-db
```

### 3. Set Up Databases

Before running evaluations, you need to set up the PostgreSQL databases from the dump files:

```bash
# Set up all databases (this may take a while)
poetry run sens bird-critic setup-db

# Set up only the first 5 databases for testing
poetry run sens bird-critic setup-db --limit 5

# Clean up existing databases and start fresh
poetry run sens bird-critic setup-db --cleanup
```

This will create databases with names like `bird_0`, `bird_1`, etc.

### 4. Configure Database Connection

Make sure your `.env` file has the correct PostgreSQL connection settings:

```env
SENS_DB_HOST=localhost
SENS_DB_PORT=5432
SENS_DB_USER=your_username
SENS_DB_PASSWORD=your_password
```

## Running Evaluations

### Basic Evaluation

Run a basic evaluation on a subset of tasks:

```bash
# Evaluate first 10 tasks
poetry run sens bird-critic evaluate --limit 10

# Evaluate all tasks (530 total - this will take a while!)
poetry run sens bird-critic evaluate

# Save results to a specific file
poetry run sens bird-critic evaluate --limit 50 --output my_results.json
```

### Analyzing Results

After running an evaluation, you can analyze the results:

```bash
# Analyze results from a previous evaluation
poetry run sens bird-critic analyze bird_critic_results.json
```

The analysis will show:
- Overall success rate
- Execution time statistics
- Error type breakdown
- Per-database success rates

## Example Usage

```bash
# Complete workflow
poetry run sens bird-critic setup-db --limit 5
poetry run sens bird-critic evaluate --limit 10 --output test_results.json
poetry run sens bird-critic analyze test_results.json
```

## Understanding the Results

### Success Metrics

- **Execution Success**: Whether the generated SQL executed without errors
- **Success Rate**: Percentage of tasks that executed successfully
- **Average Execution Time**: Mean time to execute generated SQL

### Error Analysis

Common error types you might see:
- **Syntax Error**: Generated SQL has syntax issues
- **Schema Error**: SQL references non-existent tables/columns
- **Permission Error**: Database access issues
- **Connection Error**: Database connection problems

### Per-Database Analysis

Different databases in BIRD-CRITIC have varying complexity:
- Some databases have simple schemas (few tables)
- Others have complex schemas with many relationships
- Success rates may vary significantly between databases

## Database Structure

The BIRD-CRITIC dataset includes databases from various domains:
- Financial data (accounts, transactions)
- Social media (posts, comments, users)
- Educational (students, courses)
- E-commerce (products, orders)
- And more...

Each database comes with:
- Complete schema definitions
- Sample data
- Realistic relationships and constraints

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check your PostgreSQL connection settings
   - Ensure PostgreSQL is running
   - Verify user permissions

2. **Schema File Not Found**
   - Run `poetry run sens bird-critic setup-db` first
   - Check that `external/BIRD-CRITIC-1/` directory exists

3. **Memory Issues with Large Evaluations**
   - Use `--limit` to evaluate smaller batches
   - Consider running evaluations in chunks

4. **Slow Evaluation Performance**
   - Each task requires database queries and LLM calls
   - Use smaller limits for initial testing
   - Consider running overnight for full evaluations

### Debug Mode

For debugging specific issues, you can examine the generated SQL and errors in the results JSON file:

```json
{
  "task_id": "PostgreSQL_0",
  "db_id": "0",
  "query": "How many accounts are there?",
  "generated_sql": "SELECT COUNT(*) FROM account",
  "execution_success": true,
  "execution_error": null,
  "result_count": 1,
  "execution_time_ms": 45.2
}
```

## Performance Expectations

- **Setup Time**: 10-30 minutes for all databases
- **Evaluation Time**:
  - ~1-2 seconds per task
  - 10 tasks: ~30 seconds
  - 100 tasks: ~5 minutes
  - 530 tasks: ~20-30 minutes

## Integration with SENS

The BIRD-CRITIC evaluation system integrates with the existing SENS pipeline:
- Uses the same `EnhancedNL2SQLPipeline` for SQL generation
- Leverages existing schema context and retrieval systems
- Supports all SENS configuration options
- Works with the same database connection settings

This allows you to evaluate how well SENS performs on real-world, challenging SQL scenarios.
