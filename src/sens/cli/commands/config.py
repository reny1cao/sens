"""Configuration management commands for Sens CLI.

This module provides commands for managing Sens configuration,
including API keys and other settings.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


def handle_config_set(key: str, value: str) -> None:
    """Set a configuration value in the .env file.

    Args:
        key: Configuration key (e.g., 'api_key')
        value: Configuration value
    """
    # Map friendly names to environment variables
    key_mapping = {
        "api_key": "SENS_OPENROUTER_API_KEY",
        "api-key": "SENS_OPENROUTER_API_KEY",
        "openrouter_api_key": "SENS_OPENROUTER_API_KEY",
        "model": "SENS_SQL_GENERATOR__PRIMARY_MODEL",
        "primary_model": "SENS_SQL_GENERATOR__PRIMARY_MODEL",
        "fallback_model": "SENS_SQL_GENERATOR__FALLBACK_MODEL",
        "confidence_threshold": "SENS_INTENT_EXTRACTOR__CONFIDENCE_THRESHOLD",
        "log_level": "SENS_LOG_LEVEL",
        "environment": "SENS_ENVIRONMENT",
    }

    # Get the actual environment variable name
    env_var = key_mapping.get(key.lower(), f"SENS_{key.upper()}")

    # Find the .env file
    env_path = Path(".env")
    if not env_path.exists():
        # Try to find it in parent directories
        current = Path.cwd()
        while current != current.parent:
            potential_env = current / ".env"
            if potential_env.exists():
                env_path = potential_env
                break
            current = current.parent

    # Read existing .env content if it exists
    env_content = []
    if env_path.exists():
        with open(env_path, "r") as f:
            env_content = f.readlines()
    else:
        # Create from .env.example if available
        example_path = env_path.parent / ".env.example"
        if example_path.exists():
            with open(example_path, "r") as f:
                env_content = f.readlines()
            log.info("created_env_from_example", path=str(env_path))

    # Update or add the configuration
    found = False
    for i, line in enumerate(env_content):
        if line.strip().startswith(f"{env_var}=") or line.strip().startswith(
            f"# {env_var}="
        ):
            # Update existing line
            env_content[i] = f"{env_var}={value}\n"
            found = True
            break

    if not found:
        # Add new configuration
        # Find a good place to insert it
        if key.lower() in ["api_key", "api-key", "openrouter_api_key"]:
            # Insert after OpenRouter configuration comment
            for i, line in enumerate(env_content):
                if "OpenRouter Configuration" in line:
                    # Find the next empty line or comment
                    j = i + 1
                    while j < len(env_content) and env_content[j].strip():
                        j += 1
                    env_content.insert(j, f"{env_var}={value}\n")
                    found = True
                    break

        if not found:
            # Just append to the end
            if env_content and not env_content[-1].endswith("\n"):
                env_content.append("\n")
            env_content.append(f"{env_var}={value}\n")

    # Write back to file
    with open(env_path, "w") as f:
        f.writelines(env_content)

    # Also set in current environment
    os.environ[env_var] = value

    log.info("config_updated", key=key, env_var=env_var, path=str(env_path))
    print(f"✓ Configuration updated: {key} -> {env_var}")
    print(f"  Saved to: {env_path}")

    # Special handling for API key
    if env_var == "SENS_OPENROUTER_API_KEY":
        masked_value = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
        print(f"  API Key: {masked_value}")
        print("\n💡 Note: The configuration has been saved to .env file.")
        print("   If the application still can't find the API key, try one of these:")
        print("   1. Run from the project root directory where .env is located")
        print("   2. Export the variable: export SENS_OPENROUTER_API_KEY='your-key'")
        print("   3. Use python-dotenv: pip install python-dotenv")


def handle_config_get(key: Optional[str] = None) -> None:
    """Get configuration value(s).

    Args:
        key: Optional specific key to get. If None, shows all config.
    """
    from sens.settings import get_settings

    settings = get_settings()

    if key:
        # Map friendly names
        key_mapping = {
            "api_key": "openrouter_api_key",
            "api-key": "openrouter_api_key",
            "model": "sql_generator.primary_model",
            "primary_model": "sql_generator.primary_model",
            "fallback_model": "sql_generator.fallback_model",
            "confidence_threshold": "intent_extractor.confidence_threshold",
            "log_level": "logging.level",
            "environment": "environment",
        }

        mapped_key = key_mapping.get(key.lower(), key)

        # Navigate nested settings
        value = settings
        for part in mapped_key.split("."):
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                print(f"Configuration key not found: {key}")
                sys.exit(1)

        # Mask sensitive values
        if "api_key" in key.lower() and value:
            value = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"

        print(f"{key}: {value}")
    else:
        # Show all configuration
        print("Current Configuration:")
        print("-" * 50)

        # API Configuration
        api_key = settings.openrouter_api_key
        if api_key:
            masked_key = (
                api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
            )
            print(f"API Key: {masked_key}")
        else:
            print("API Key: NOT SET")

        print(f"API Base URL: {settings.openrouter_base_url}")

        # Model Configuration
        print("\nModels:")
        print(f"  Primary Model: {settings.sql_generator.primary_model}")
        print(f"  Fallback Model: {settings.sql_generator.fallback_model}")
        print(
            f"  Confidence Threshold: {settings.intent_extractor.confidence_threshold}"
        )

        # Environment
        print("\nEnvironment:")
        print(f"  Environment: {settings.environment}")
        print(f"  Log Level: {settings.logging.level}")
        print(f"  Log Format: {settings.logging.format}")

        # Paths
        print("\nPaths:")
        print(f"  Schema Path: {settings.schema_path}")
        print(f"  Index Directory: {settings.index_dir}")


def handle_config_command(args, log: structlog.BoundLogger) -> None:
    """Handle config command and subcommands.

    Args:
        args: Parsed command line arguments
        log: Logger instance
    """
    if args.config_command == "set":
        if not args.key or not args.value:
            print("Error: Both key and value are required for 'config set'")
            print("Usage: sens config set <key> <value>")
            print("\nExample: sens config set api_key sk-or-v1-...")
            sys.exit(1)
        handle_config_set(args.key, args.value)
    elif args.config_command == "get":
        handle_config_get(args.key)
    else:
        print("Usage: sens config <set|get> [options]")
        print("\nCommands:")
        print("  set <key> <value>  Set a configuration value")
        print("  get [key]          Get configuration value(s)")
