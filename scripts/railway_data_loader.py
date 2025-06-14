#!/usr/bin/env python3
"""
Railway-specific data loader that handles environment setup and loading.
Can be run locally with Railway credentials or directly in Railway.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if we're in Railway environment
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None


def setup_railway_env():
    """Set up environment for Railway database connection."""
    if IS_RAILWAY:
        print("🚂 Running in Railway environment")
        # Railway auto-injects these
        return

    # For local development with Railway DB
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        print("📡 Using DATABASE_URL for connection")
        # Parse DATABASE_URL to individual components if needed
        from urllib.parse import urlparse

        parsed = urlparse(database_url)

        os.environ["SENS_DB_HOST"] = parsed.hostname or "localhost"
        os.environ["SENS_DB_PORT"] = str(parsed.port or 5432)
        os.environ["SENS_DB_NAME"] = parsed.path.lstrip("/")
        os.environ["SENS_DB_USER"] = parsed.username or "postgres"
        os.environ["SENS_DB_PASSWORD"] = parsed.password or ""

        print(f"  Host: {parsed.hostname}")
        print(f"  Port: {parsed.port}")
        print(f"  Database: {parsed.path.lstrip('/')}")
    else:
        print("⚠️  No DATABASE_URL found. Using individual SENS_DB_* variables.")
        print("   For Railway: run 'railway run python scripts/railway_data_loader.py'")


async def main():
    """Main entry point for Railway data loading."""
    print("🚀 SENS Railway Data Loader")
    print("=" * 50)

    # Set up environment
    setup_railway_env()

    # Import here after environment setup
    from sens.datasource.financial import FinancialDataLoader

    # Check what to load
    load_type = os.getenv("LOAD_TYPE", "minimal").lower()

    if load_type == "minimal":
        print("Loading minimal test data (3 symbols)...")
        from load_minimal_test_data import load_test_data

        await load_test_data()

    elif load_type == "quick":
        print("Loading quick start data (~35 symbols)...")
        from quick_start_loader import quick_start_load

        await quick_start_load()

    elif load_type == "full":
        print("Loading comprehensive data (100+ symbols)...")
        from comprehensive_data_loader import comprehensive_load

        await comprehensive_load()

    else:
        print(f"Unknown load type: {load_type}")
        print("Use LOAD_TYPE=minimal|quick|full")
        sys.exit(1)

    print("\n✅ Data loading complete!")


if __name__ == "__main__":
    asyncio.run(main())
