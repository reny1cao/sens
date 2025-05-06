# Integration Tests

This directory contains integration tests that verify the complete functionality of various components by making actual API calls and database interactions.

## Requirements

1. Valid API credentials
2. Environment variables properly configured
3. Test database (if applicable)

## Environment Setup

Before running integration tests, ensure you have the following environment variables set:

```bash
SENS_LLM_API_KEY=your_openrouter_api_key
```

## Running Tests

To run all integration tests:

```bash
pytest tests/integration -v
```

To run specific test files:

```bash
pytest tests/integration/test_sql_generator_integration.py -v
```

To run a specific test:

```bash
pytest tests/integration/test_sql_generator_integration.py::test_basic_sql_generation -v
```

## Test Categories

### SQL Generator Integration Tests

Located in `test_sql_generator_integration.py`, these tests verify:

1. Basic SQL generation
2. Complex query handling
3. Error scenarios
4. Model fallback behavior
5. Token usage tracking

These tests make actual API calls to OpenRouter and will be skipped if no API key is provided.

## Adding New Tests

When adding new integration tests:

1. Use the `@pytest.mark.integration` decorator
2. Add appropriate environment variable checks
3. Document any new environment variables in this README
4. Include both success and error scenarios
5. Clean up any test resources in teardown

## Best Practices

1. Never commit API keys or sensitive credentials
2. Use pytest fixtures for common setup
3. Clean up any test data after tests complete
4. Add appropriate timeouts for API calls
5. Include both positive and negative test cases
