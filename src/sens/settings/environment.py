"""Environment-specific configuration utilities.

This module provides utilities to validate and configure environment-specific settings,
particularly for database connections across different deployment environments.
"""

import os
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


def get_environment_info() -> Dict[str, Any]:
    """Get current environment information and database configuration status."""
    env = os.getenv("SENS_ENVIRONMENT", "development")
    database_url = os.getenv("DATABASE_URL")

    # Local database settings
    local_db_config = {
        "host": os.getenv("SENS_DB_HOST", "localhost"),
        "port": int(os.getenv("SENS_DB_PORT", "5432")),
        "name": os.getenv("SENS_DB_NAME", "postgres"),
        "user": os.getenv("SENS_DB_USER", "postgres"),
        "password": os.getenv("SENS_DB_PASSWORD", ""),
    }

    # Determine which database configuration is active
    using_railway = database_url is not None
    using_local = not using_railway or bool(local_db_config["password"])

    return {
        "environment": env,
        "database_source": "railway" if using_railway and not using_local else "local",
        "railway_url_available": using_railway,
        "local_config_complete": all(
            [
                local_db_config["host"],
                str(local_db_config["port"]),
                local_db_config["name"],
                local_db_config["user"],
            ]
        ),
        "local_db_config": local_db_config,
        "railway_url": database_url[:50] + "..." if database_url else None,
    }


def validate_bird_critic_environment() -> bool:
    """Validate that the environment is properly configured for BIRD-CRITIC evaluation.

    BIRD-CRITIC evaluation requires local PostgreSQL access to create and manage
    multiple databases with bird_ prefix.

    Returns:
        True if environment is properly configured for BIRD-CRITIC evaluation
    """
    env_info = get_environment_info()

    # For BIRD-CRITIC, we need local PostgreSQL access
    if env_info["database_source"] != "local":
        logger.warning(
            "BIRD-CRITIC evaluation requires local PostgreSQL access",
            current_source=env_info["database_source"],
            suggestion="Set SENS_DB_HOST, SENS_DB_PORT, SENS_DB_USER, SENS_DB_NAME and optionally SENS_DB_PASSWORD",
        )
        return False

    if not env_info["local_config_complete"]:
        logger.warning(
            "Incomplete local database configuration for BIRD-CRITIC",
            missing_fields=[
                k
                for k, v in env_info["local_db_config"].items()
                if not v and k != "password"
            ],
        )
        return False

    logger.info(
        "Environment properly configured for BIRD-CRITIC evaluation",
        database_host=env_info["local_db_config"]["host"],
        database_port=env_info["local_db_config"]["port"],
        database_user=env_info["local_db_config"]["user"],
    )
    return True


def log_environment_status() -> None:
    """Log current environment configuration status."""
    env_info = get_environment_info()

    logger.info(
        "Environment configuration status",
        environment=env_info["environment"],
        database_source=env_info["database_source"],
        railway_available=env_info["railway_url_available"],
        local_config_complete=env_info["local_config_complete"],
    )

    if (
        env_info["environment"] == "development"
        and env_info["database_source"] == "railway"
    ):
        logger.warning(
            "Development environment using Railway database",
            suggestion="Consider using local PostgreSQL for development by setting SENS_DB_* variables",
        )

    if (
        env_info["environment"] in ["staging", "production"]
        and env_info["database_source"] == "local"
    ):
        logger.warning(
            "Production/staging environment using local database",
            suggestion="Ensure DATABASE_URL is properly configured for production deployments",
        )
