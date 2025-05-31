"""Base interface for schema extractors."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import time
import structlog

from sens.schema.unified_schema import UnifiedSchema, DataSourceType

logger = structlog.get_logger(__name__)


class SchemaExtractor(ABC):
    """Abstract base class for schema extractors."""
    
    def __init__(self, source_type: DataSourceType, source_id: str):
        """Initialize extractor with source information.
        
        Args:
            source_type: Type of data source
            source_id: Unique identifier for this source
        """
        self.source_type = source_type
        self.source_id = source_id
    
    @abstractmethod
    async def extract(self) -> UnifiedSchema:
        """Extract schema from the data source.
        
        Returns:
            UnifiedSchema containing all schema information
            
        Raises:
            SchemaExtractionError: If extraction fails
        """
        pass
    
    async def extract_with_timing(self) -> UnifiedSchema:
        """Extract schema and record timing information."""
        start_time = time.time()
        
        try:
            logger.info("schema_extraction_started", 
                       source_type=self.source_type.value,
                       source_id=self.source_id)
            
            schema = await self.extract()
            
            # Add timing information
            duration_ms = int((time.time() - start_time) * 1000)
            schema.extraction_duration_ms = duration_ms
            
            logger.info("schema_extraction_completed",
                       source_type=self.source_type.value,
                       source_id=self.source_id,
                       duration_ms=duration_ms,
                       table_count=len(schema.tables))
            
            return schema
            
        except Exception as e:
            logger.error("schema_extraction_failed",
                        source_type=self.source_type.value,
                        source_id=self.source_id,
                        error=str(e))
            raise SchemaExtractionError(
                f"Failed to extract schema from {self.source_type.value}: {str(e)}"
            ) from e


class SchemaExtractionError(Exception):
    """Raised when schema extraction fails."""
    pass