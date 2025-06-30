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

logger = logging.getLogger(__name__)


class BirdDatabaseSetup:
    """Manages PostgreSQL database setup for BIRD-CRITIC evaluation."""

    def __init__(
        self,
        db_host: str = "localhost",
        db_port: int = 5432,
        db_user: str = "postgres",
        db_password: str = "",
        dumps_directory: str = "external/BIRD-CRITIC-1/evaluation/postgre_table_dumps",
    ):
        """
        Initialize database setup.

        Args:
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_user: PostgreSQL user
            db_password: PostgreSQL password
            dumps_directory: Directory containing SQL dump files
        """
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.dumps_dir = Path(dumps_directory)
        if not self.dumps_dir.exists():
            raise FileNotFoundError(f"Dumps directory not found: {dumps_directory}")

    def _get_admin_connection(self) -> psycopg2.extensions.connection:
        """Get administrative connection to PostgreSQL."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database="postgres",  # Connect to default database
                user=self.db_user,
                password=self.db_password,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except psycopg2.Error as e:
            raise ExecutionError(f"Failed to connect to PostgreSQL: {e}")

    def list_available_dumps(self) -> List[str]:
        """List all available database templates."""
        dumps = []
        for template_dir in self.dumps_dir.iterdir():
            if template_dir.is_dir() and template_dir.name.endswith("_template"):
                # Remove the '_template' suffix to get the db_id
                db_id = template_dir.name.replace("_template", "")
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
        Restore a database from SQL dump files in template directory.

        Args:
            db_id: Database ID (corresponds to template directory)
            database_prefix: Prefix for the created database name

        Returns:
            True if successful, False otherwise
        """
        template_dir = self.dumps_dir / f"{db_id}_template"
        if not template_dir.exists():
            logger.error(f"Template directory not found: {template_dir}")
            return False

        # Get all SQL files in the template directory
        sql_files = list(template_dir.glob("*.sql"))
        if not sql_files:
            logger.error(f"No SQL files found in template directory: {template_dir}")
            return False

        db_name = f"{database_prefix}{db_id}"

        # Create the database
        if not self.create_database(db_name, drop_if_exists=True):
            logger.error(f"Failed to create database: {db_name}")
            return False

        # Restore from dump files using psql
        try:
            env = {"PGPASSWORD": self.db_password} if self.db_password else None

            logger.info(f"Restoring {len(sql_files)} SQL files to database {db_name}")

            # Execute each SQL file
            for sql_file in sorted(sql_files):
                cmd = [
                    "psql",
                    "-h",
                    self.db_host,
                    "-p",
                    str(self.db_port),
                    "-U",
                    self.db_user,
                    "-d",
                    db_name,
                    "-f",
                    str(sql_file),
                    "-q",  # Quiet mode
                ]

                logger.debug(f"Executing SQL file: {sql_file.name}")
                result = subprocess.run(
                    cmd, env=env, capture_output=True, text=True, check=False
                )

                if result.returncode != 0:
                    logger.error(f"Failed to execute {sql_file.name}: {result.stderr}")
                    return False

            logger.info(f"Successfully restored database {db_name}")
            return True

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
    import os

    parser = argparse.ArgumentParser(description="Set up BIRD-CRITIC databases")
    parser.add_argument(
        "--cleanup", action="store_true", help="Clean up existing databases"
    )
    parser.add_argument("--limit", type=int, help="Limit number of databases to set up")
    parser.add_argument("--prefix", default="bird_", help="Database name prefix")
    parser.add_argument("--db-host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--db-port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--db-user", default="postgres", help="PostgreSQL user")
    parser.add_argument("--db-password", default="", help="PostgreSQL password")

    args = parser.parse_args()

    # Use environment variables if available, otherwise use command line args
    db_host = os.getenv("SENS_DB_HOST", args.db_host)
    db_port = int(os.getenv("SENS_DB_PORT", args.db_port))
    db_user = os.getenv("SENS_DB_USER", args.db_user)
    db_password = os.getenv("SENS_DB_PASSWORD", args.db_password)

    setup = BirdDatabaseSetup(
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_password=db_password,
    )

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
