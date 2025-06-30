"""
Database setup utilities for BIRD-CRITIC evaluation.

This module provides functionality to set up PostgreSQL databases
from the BIRD-CRITIC dump files.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from sens.exceptions import ExecutionError
from sens.settings import get_settings

logger = logging.getLogger(__name__)


class BirdDatabaseSetup:
    """Manages PostgreSQL database setup for BIRD-CRITIC evaluation."""

    def __init__(
        self,
        settings=None,
        dumps_directory: str = "external/BIRD-CRITIC-1/evaluation/postgre_table_dumps",
    ):
        """
        Initialize database setup.

        Args:
            settings: SENS settings configuration (optional, will use defaults)
            dumps_directory: Directory containing SQL dump files
        """
        self.settings = settings or get_settings()
        self.dumps_dir = Path(dumps_directory)
        if not self.dumps_dir.exists():
            raise FileNotFoundError(f"Dumps directory not found: {dumps_directory}")

    def _get_admin_connection(self) -> psycopg2.extensions.connection:
        """Get administrative connection to PostgreSQL."""
        try:
            conn = psycopg2.connect(
                host=self.settings.db_host,
                port=self.settings.db_port,
                database="postgres",  # Connect to default database
                user=self.settings.db_user,
                password=self.settings.db_password,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except psycopg2.Error as e:
            raise ExecutionError(f"Failed to connect to PostgreSQL: {e}")

    def list_available_dumps(self) -> List[str]:
        """List all available SQL dump files."""
        dumps = []
        for dump_file in self.dumps_dir.glob("*.sql"):
            db_id = dump_file.stem
            dumps.append(db_id)
        return sorted(dumps)

    def database_exists(self, db_name: str) -> bool:
        """Check if a database exists."""
        conn = self._get_admin_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
                )
                exists = cursor.fetchone() is not None
            return exists
        finally:
            conn.close()

    def create_database(self, db_name: str, drop_if_exists: bool = False) -> bool:
        """
        Create a new database.

        Args:
            db_name: Name of the database to create
            drop_if_exists: Whether to drop the database if it already exists

        Returns:
            True if database was created, False if it already existed
        """
        conn = self._get_admin_connection()
        try:
            if self.database_exists(db_name):
                if drop_if_exists:
                    logger.info(f"Dropping existing database: {db_name}")
                    with conn.cursor() as cursor:
                        cursor.execute(f'DROP DATABASE "{db_name}"')
                else:
                    logger.info(f"Database already exists: {db_name}")
                    return False

            logger.info(f"Creating database: {db_name}")
            with conn.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE "{db_name}"')
            return True

        finally:
            conn.close()

    def restore_dump(self, db_id: str, database_prefix: str = "bird_") -> bool:
        """
        Restore a database from SQL dump file.

        Args:
            db_id: Database ID (corresponds to dump filename)
            database_prefix: Prefix for the created database name

        Returns:
            True if successful, False otherwise
        """
        dump_file = self.dumps_dir / f"{db_id}.sql"
        if not dump_file.exists():
            logger.error(f"Dump file not found: {dump_file}")
            return False

        db_name = f"{database_prefix}{db_id}"

        # Create the database
        if not self.create_database(db_name, drop_if_exists=True):
            logger.error(f"Failed to create database: {db_name}")
            return False

        # Restore from dump using psql
        try:
            cmd = [
                "psql",
                "-h",
                self.settings.db_host,
                "-p",
                str(self.settings.db_port),
                "-U",
                self.settings.db_user,
                "-d",
                db_name,
                "-f",
                str(dump_file),
                "-q",  # Quiet mode
            ]

            env = (
                {"PGPASSWORD": self.settings.db_password}
                if self.settings.db_password
                else None
            )

            logger.info(f"Restoring dump {dump_file} to database {db_name}")
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                logger.info(f"Successfully restored database {db_name}")
                return True
            else:
                logger.error(f"Failed to restore database {db_name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error restoring database {db_name}: {e}")
            return False

    def setup_all_databases(
        self, database_prefix: str = "bird_", limit: Optional[int] = None
    ) -> List[str]:
        """
        Set up all available databases from dump files.

        Args:
            database_prefix: Prefix for created database names
            limit: Maximum number of databases to set up (for testing)

        Returns:
            List of successfully created database names
        """
        dumps = self.list_available_dumps()
        if limit:
            dumps = dumps[:limit]

        successful = []
        failed = []

        logger.info(
            f"Setting up {len(dumps)} databases with prefix '{database_prefix}'"
        )

        for i, db_id in enumerate(dumps, 1):
            logger.info(f"Progress: {i}/{len(dumps)} - Setting up database for {db_id}")

            if self.restore_dump(db_id, database_prefix):
                successful.append(f"{database_prefix}{db_id}")
            else:
                failed.append(db_id)

        logger.info("Database setup complete!")
        logger.info(f"Successful: {len(successful)}")
        logger.info(f"Failed: {len(failed)}")

        if failed:
            logger.warning(f"Failed to set up databases for: {', '.join(failed)}")

        return successful

    def cleanup_databases(self, database_prefix: str = "bird_") -> int:
        """
        Remove all databases with the given prefix.

        Args:
            database_prefix: Prefix of databases to remove

        Returns:
            Number of databases removed
        """
        conn = self._get_admin_connection()
        removed = 0

        try:
            with conn.cursor() as cursor:
                # Find databases with the prefix
                cursor.execute(
                    "SELECT datname FROM pg_database WHERE datname LIKE %s",
                    (f"{database_prefix}%",),
                )
                databases = [row[0] for row in cursor.fetchall()]

            for db_name in databases:
                logger.info(f"Dropping database: {db_name}")
                with conn.cursor() as cursor:
                    cursor.execute(f'DROP DATABASE "{db_name}"')
                removed += 1

            logger.info(f"Cleaned up {removed} databases")
            return removed

        finally:
            conn.close()


def main():
    """Main setup function."""
    import argparse

    parser = argparse.ArgumentParser(description="Set up BIRD-CRITIC databases")
    parser.add_argument(
        "--cleanup", action="store_true", help="Clean up existing databases"
    )
    parser.add_argument("--limit", type=int, help="Limit number of databases to set up")
    parser.add_argument("--prefix", default="bird_", help="Database name prefix")

    args = parser.parse_args()

    settings = get_settings()
    setup = BirdDatabaseSetup(settings)

    if args.cleanup:
        setup.cleanup_databases(args.prefix)
        return

    # List available dumps
    dumps = setup.list_available_dumps()
    print(f"Found {len(dumps)} dump files:")
    for dump in dumps[:10]:  # Show first 10
        print(f"  - {dump}")
    if len(dumps) > 10:
        print(f"  ... and {len(dumps) - 10} more")

    # Set up databases
    successful = setup.setup_all_databases(args.prefix, args.limit)
    print(f"\nSuccessfully set up {len(successful)} databases")


if __name__ == "__main__":
    main()
