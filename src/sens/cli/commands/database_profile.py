"""
Database profiling command for semantic understanding.
"""

import asyncio
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

import structlog

from sens.learning.database_explorer import DatabaseExplorer
from sens.learning.lightrag_api_client import LightRAGAPIClient
from sens.learning.semantic_storage import SemanticStorageManager

log = structlog.get_logger()


class DatabaseProfiler:
    """Professional database profiling service."""

    def __init__(self, lightrag_url: str = "http://127.0.0.1:9621"):
        self.lightrag_url = lightrag_url
        self.lightrag_client = None
        self.storage_manager = None
        self.explorer = None

    async def initialize(self) -> bool:
        """Initialize the profiler services."""
        try:
            self.lightrag_client = LightRAGAPIClient(self.lightrag_url)
            await self.lightrag_client.check_health()

            self.storage_manager = SemanticStorageManager(self.lightrag_client)
            self.explorer = DatabaseExplorer(self.lightrag_client)

            log.info("database_profiler_initialized", lightrag_url=self.lightrag_url)
            return True
        except Exception as e:
            log.error("profiler_initialization_failed", error=str(e))
            return False

    async def profile_database(
        self, db_path: str, db_name: Optional[str] = None
    ) -> Dict:
        """Profile a single database and store semantic understanding."""
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")

        if not db_name:
            db_name = Path(db_path).stem

        log.info("profiling_database", db_path=db_path, db_name=db_name)
        start_time = time.time()

        # Create async database connection
        db_connection = AsyncSQLiteConnection(db_path)

        try:
            # Perform systematic exploration
            table_profiles = await self.explorer.explore_database(
                db_connection, max_tables=50
            )

            if not table_profiles:
                log.warning("no_tables_found", db_path=db_path)
                return {"status": "no_tables", "tables_profiled": 0}

            # Store semantic understanding
            chunks_stored = 0
            for table_name, profile in table_profiles.items():
                chunk_id = await self.storage_manager.store_table_understanding(profile)
                chunks_stored += 1

                # Store domain classifications as business rules
                for domain in profile.business_domain_hints:
                    await self.storage_manager.store_business_rule(
                        rule_description=f"Table {table_name} contains {domain} domain data",
                        rule_type="DOMAIN_CLASSIFICATION",
                        applies_to=[table_name],
                        confidence=0.8,
                    )
                    chunks_stored += 1

            profiling_time = (time.time() - start_time) * 1000

            result = {
                "status": "success",
                "db_name": db_name,
                "db_path": db_path,
                "tables_profiled": len(table_profiles),
                "chunks_stored": chunks_stored,
                "profiling_time_ms": profiling_time,
                "table_profiles": {
                    name: {
                        "row_count": profile.row_count,
                        "column_count": profile.column_count,
                        "entity_types": profile.entity_type_hints,
                        "business_domains": profile.business_domain_hints,
                    }
                    for name, profile in table_profiles.items()
                },
            }

            log.info(
                "database_profiled_successfully",
                db_name=db_name,
                tables=len(table_profiles),
                chunks=chunks_stored,
                time_ms=profiling_time,
            )

            return result

        finally:
            db_connection.close()

    async def profile_bird_databases(self, bird_directory: str) -> Dict:
        """Profile all BIRD SQL databases."""
        bird_path = Path(bird_directory)
        if not bird_path.exists():
            raise FileNotFoundError(f"BIRD directory not found: {bird_directory}")

        dev_databases = bird_path / "dev_databases"
        if not dev_databases.exists():
            raise FileNotFoundError(f"BIRD dev_databases not found: {dev_databases}")

        log.info("profiling_bird_databases", directory=str(dev_databases))

        results = {}
        total_tables = 0
        total_chunks = 0

        # Find all SQLite databases
        for db_dir in dev_databases.iterdir():
            if not db_dir.is_dir():
                continue

            sqlite_files = list(db_dir.glob("*.sqlite"))
            if not sqlite_files:
                continue

            db_path = str(sqlite_files[0])
            db_name = db_dir.name

            try:
                result = await self.profile_database(db_path, db_name)
                results[db_name] = result

                if result["status"] == "success":
                    total_tables += result["tables_profiled"]
                    total_chunks += result["chunks_stored"]

            except Exception as e:
                log.error("database_profiling_failed", db_name=db_name, error=str(e))
                results[db_name] = {"status": "error", "error": str(e)}

        summary = {
            "databases_profiled": len(
                [r for r in results.values() if r["status"] == "success"]
            ),
            "total_databases": len(results),
            "total_tables": total_tables,
            "total_chunks": total_chunks,
            "results": results,
        }

        log.info("bird_profiling_completed", **summary)
        return summary


class AsyncSQLiteConnection:
    """Async SQLite connection wrapper."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query: str):
        try:
            cursor = self.conn.execute(query)
            return AsyncCursor(cursor)
        except Exception as e:
            log.error("sql_execution_failed", query=query[:100], error=str(e))
            raise

    def close(self):
        self.conn.close()


class AsyncCursor:
    """Async cursor wrapper with context manager support."""

    def __init__(self, cursor):
        self.cursor = cursor
        self.rows = None
        self.index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def fetchone(self):
        return self.cursor.fetchone()

    async def fetchall(self):
        return self.cursor.fetchall()

    def __aiter__(self):
        if self.rows is None:
            self.rows = self.cursor.fetchall()
        self.index = 0
        return self

    async def __anext__(self):
        if self.rows is None:
            self.rows = self.cursor.fetchall()

        if self.index < len(self.rows):
            row = self.rows[self.index]
            self.index += 1
            return row
        else:
            raise StopAsyncIteration


async def handle_profile_database_command(args) -> int:
    """Handle the database profiling CLI command."""
    profiler = DatabaseProfiler(lightrag_url=args.lightrag_url)

    if not await profiler.initialize():
        print("❌ Failed to initialize profiler. Check LightRAG server connection.")
        return 1

    try:
        if args.bird_directory:
            # Profile all BIRD databases
            print(f"🔍 Profiling BIRD databases in {args.bird_directory}")
            result = await profiler.profile_bird_databases(args.bird_directory)

            print(f"\n📊 BIRD PROFILING RESULTS:")
            print(
                f"   Databases processed: {result['databases_profiled']}/{result['total_databases']}"
            )
            print(f"   Tables profiled: {result['total_tables']}")
            print(f"   Knowledge chunks stored: {result['total_chunks']}")

            if args.detailed:
                print(f"\n📋 Database Details:")
                for db_name, db_result in result["results"].items():
                    if db_result["status"] == "success":
                        print(
                            f"   ✅ {db_name}: {db_result['tables_profiled']} tables, {db_result['chunks_stored']} chunks"
                        )
                    else:
                        print(
                            f"   ❌ {db_name}: {db_result.get('error', 'Unknown error')}"
                        )

        elif args.database_path:
            # Profile single database
            print(f"🔍 Profiling database: {args.database_path}")
            result = await profiler.profile_database(
                args.database_path, args.database_name
            )

            if result["status"] == "success":
                print(f"\n✅ PROFILING SUCCESSFUL:")
                print(f"   Database: {result['db_name']}")
                print(f"   Tables: {result['tables_profiled']}")
                print(f"   Chunks stored: {result['chunks_stored']}")
                print(f"   Time: {result['profiling_time_ms']:.1f}ms")

                if args.detailed:
                    print(f"\n📋 Table Details:")
                    for table_name, profile in result["table_profiles"].items():
                        domains = (
                            ", ".join(profile["business_domains"])
                            if profile["business_domains"]
                            else "General"
                        )
                        entity_types = (
                            ", ".join(profile["entity_types"])
                            if profile["entity_types"]
                            else "Unknown"
                        )
                        print(
                            f"   {table_name}: {profile['row_count']:,} rows, {domains} domain, {entity_types}"
                        )
            else:
                print(f"❌ Profiling failed: {result}")
                return 1

        else:
            print("❌ Must specify either --database-path or --bird-directory")
            return 1

        print(
            f"\n🧠 Semantic knowledge has been stored in LightRAG for intelligent query understanding."
        )
        return 0

    except Exception as e:
        print(f"❌ Profiling failed: {e}")
        log.error("database_profiling_command_failed", error=str(e))
        return 1
