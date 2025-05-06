"""Configuration for integration tests."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def pytest_configure(config):
    """Configure pytest for integration tests."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that makes external API calls",
    )


@pytest.fixture(scope="session")
def integration_env():
    """Verify and provide integration test environment variables."""
    required_vars = ["SENS_LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        pytest.skip(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return {var: os.getenv(var) for var in required_vars}


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory."""
    data_dir = Path(__file__).parent / "test_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Clean up any resources after each test."""
    yield
    # Add any cleanup code here if needed in the future
