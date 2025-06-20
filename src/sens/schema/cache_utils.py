"""Utilities for schema caching with version detection."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

from sens.schema.unified_schema import UnifiedSchema

logger = structlog.get_logger(__name__)


class SchemaCache:
    """Utility for managing schema cache with version detection."""

    @staticmethod
    def generate_schema_version(db_config: Dict[str, Any]) -> str:
        """Generate a version hash based on database configuration.

        This ensures cache is invalidated when switching databases.
        """
        # Include key database identifiers in version
        version_data = {
            "host": db_config.get("host", ""),
            "port": db_config.get("port", ""),
            "database": db_config.get("database", db_config.get("name", "")),
            "user": db_config.get("user", ""),
            # Don't include password in version hash
        }

        version_str = json.dumps(version_data, sort_keys=True)
        return hashlib.sha256(version_str.encode()).hexdigest()[:16]

    @staticmethod
    def get_cache_key(
        source_id: str, db_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate cache key for schema including version."""
        base_key = f"schema:{source_id}"

        if db_config:
            version = SchemaCache.generate_schema_version(db_config)
            return f"{base_key}:v{version}"

        return base_key

    @staticmethod
    async def should_refresh_schema(
        cached_schema: UnifiedSchema, max_age_hours: int = 24
    ) -> bool:
        """Check if cached schema should be refreshed."""
        if not cached_schema.extracted_at:
            return True

        # Check age
        age = datetime.utcnow() - cached_schema.extracted_at
        if age > timedelta(hours=max_age_hours):
            logger.info(
                "schema_cache_expired",
                age_hours=age.total_seconds() / 3600,
                max_age_hours=max_age_hours,
            )
            return True

        return False

    @staticmethod
    def validate_cached_schema(schema: UnifiedSchema) -> bool:
        """Validate that cached schema is complete and valid."""
        if not schema.tables:
            logger.warning("cached_schema_has_no_tables")
            return False

        if not schema.source_id:
            logger.warning("cached_schema_has_no_source_id")
            return False

        # Check for corrupted data
        for table in schema.tables:
            if not table.name or not table.columns:
                logger.warning("cached_schema_has_invalid_table", table_name=table.name)
                return False

        return True
