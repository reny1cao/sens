#!/usr/bin/env python3
"""Test Railway database connection and schema."""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up Railway database connection
# Use environment variable or construct from individual components
database_url = os.getenv("DATABASE_URL")

if database_url:
    parsed = urlparse(database_url)
    os.environ["SENS_DB_HOST"] = parsed.hostname or "localhost"
    os.environ["SENS_DB_PORT"] = str(parsed.port or 5432)
    os.environ["SENS_DB_NAME"] = parsed.path.lstrip("/")
    os.environ["SENS_DB_USER"] = parsed.username or "postgres"
    os.environ["SENS_DB_PASSWORD"] = parsed.password or ""
else:
    # Use individual environment variables if DATABASE_URL not set
    print("⚠️  No DATABASE_URL found. Using individual SENS_DB_* variables.")
    print("   For Railway: run 'railway run python scripts/test_railway_connection.py'")


async def test_connection():
    """Test database connection and check schema."""
    print("🔍 Testing Railway Database Connection")
    print("=" * 50)

    # Import after path setup
    import psycopg2
    from psycopg2 import sql

    from sens.settings import get_settings

    settings = get_settings()

    # Show connection details (without password)
    print(f"Host: {settings.db_host}")
    print(f"Port: {settings.db_port}")
    print(f"Database: {settings.db_name}")
    print(f"User: {settings.db_user}")
    print("-" * 50)

    try:
        # Test connection
        print("Testing connection...")
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )
        cursor = conn.cursor()

        # Check PostgreSQL version
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Connected to: {version}")
        print("-" * 50)

        # Check if financial tables exist
        print("\nChecking for financial schema tables:")
        tables_query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN (
            'securities', 'daily_prices', 'economic_indicators',
            'portfolio_holdings', 'trades', 'options_contracts',
            'market_data', 'financial_statements'
        )
        ORDER BY table_name;
        """
        cursor.execute(tables_query)
        tables = cursor.fetchall()

        if tables:
            print(f"\nFound {len(tables)} financial tables:")
            for table in tables:
                # Check row count
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                print(f"  ✓ {table[0]}: {count} rows")
        else:
            print("  ❌ No financial tables found!")
            print("  Need to create schema first.")

        # Check for daily_prices partitions
        print("\nChecking daily_prices partitions:")
        partition_query = """
        SELECT
            child.relname AS partition_name
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        WHERE parent.relname = 'daily_prices'
        ORDER BY child.relname
        LIMIT 5;
        """
        cursor.execute(partition_query)
        partitions = cursor.fetchall()
        if partitions:
            print(f"  Found {len(partitions)} partitions (showing first 5):")
            for p in partitions:
                print(f"    - {p[0]}")

        cursor.close()
        conn.close()

        return len(tables) > 0

    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check if DATABASE_URL or SENS_DB_* variables are set")
        print("2. For Railway: run 'railway service' to select a service")
        print("3. Ensure PostgreSQL service is added to your Railway project")
        return False


async def create_schema_if_needed():
    """Create financial schema if it doesn't exist."""
    from sens.datasource.financial import FinancialDataLoader

    print("\n📊 Creating Financial Schema")
    print("=" * 50)

    try:
        async with FinancialDataLoader() as loader:
            await loader.ensure_schema()
            print("✅ Schema created/verified successfully!")
            return True
    except Exception as e:
        print(f"❌ Schema creation failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    # Test connection
    has_tables = await test_connection()

    if not has_tables:
        print("\n" + "=" * 50)
        print("Creating financial schema...")
        if await create_schema_if_needed():
            # Re-test to show tables
            await test_connection()

    print("\n✅ Connection test complete!")
    print("\nNext steps:")
    print("1. Set API keys: SENS_ALPHA_VANTAGE_API_KEY and SENS_FRED_API_KEY")
    print("2. Run: python scripts/railway_data_loader.py")


if __name__ == "__main__":
    asyncio.run(main())
