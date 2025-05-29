"""Multi-source SQL executor that supports different database types."""

from typing import Dict, List, Any, Optional, Union
import asyncio
from datetime import datetime

import duckdb
import structlog
from psycopg2.extras import RealDictCursor

from sens.execution.executor import SQLExecutor
from sens.execution.types import QueryResult, ExecutionMetrics
from sens.datasource.models import DataSourceType
from sens.datasource.manager import DataSource, DataSourceManager

logger = structlog.get_logger(__name__)


class MultiSourceExecutor:
    """Executor that can run SQL against multiple data source types."""
    
    def __init__(self, source_manager: DataSourceManager):
        self.source_manager = source_manager
        self.postgres_executor = SQLExecutor()
    
    async def execute(
        self,
        sql: str,
        session_id: Optional[str] = None,
        params: Optional[Dict] = None,
        timeout: int = 30
    ) -> QueryResult:
        """Execute SQL against the appropriate data source."""
        # Get the data source for this session
        source = self.source_manager.get_session_source(session_id)
        if not source:
            source = self.source_manager.get_source("default")
        
        logger.info("executing_sql", source_id=source.id, source_type=source.type.value)
        
        start_time = datetime.now()
        
        try:
            if source.type == DataSourceType.DEFAULT_POSTGRES:
                # Use existing PostgreSQL executor
                result = await self.postgres_executor.execute_query(
                    sql, 
                    params=params, 
                    timeout=timeout
                )
                return result
                
            elif source.type == DataSourceType.UPLOADED_FILE:
                # Execute against DuckDB
                result = await self._execute_duckdb(sql, source, params, timeout)
                return result
                
            else:
                raise NotImplementedError(f"Execution for {source.type} not implemented")
                
        except Exception as e:
            logger.error("sql_execution_failed", 
                        source_id=source.id, 
                        error=str(e),
                        sql=sql[:100])
            raise
    
    async def _execute_duckdb(
        self,
        sql: str,
        source: DataSource,
        params: Optional[Dict] = None,
        timeout: int = 30
    ) -> QueryResult:
        """Execute SQL against DuckDB."""
        
        def run_query():
            conn = source.get_connection()
            
            # Set read-only mode for safety
            conn.execute("SET read_only = true")
            
            # Execute the query
            if params:
                # DuckDB uses ? for parameters
                param_values = list(params.values())
                result = conn.execute(sql, param_values)
            else:
                result = conn.execute(sql)
            
            # Fetch results
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchall()
            
            # Convert to list of dicts
            if columns:
                rows = [dict(zip(columns, row)) for row in rows]
            else:
                rows = []
            
            return columns, rows
        
        try:
            # Run query with timeout
            columns, rows = await asyncio.wait_for(
                asyncio.to_thread(run_query),
                timeout=timeout
            )
            
            execution_time = (datetime.now() - datetime.now()).total_seconds()
            
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time=execution_time,
                success=True,
                error=None,
                metrics=ExecutionMetrics(
                    execution_time=execution_time,
                    rows_returned=len(rows),
                    data_source=source.name,
                    source_type=source.type.value
                )
            )
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Query exceeded timeout of {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"DuckDB execution failed: {str(e)}")
    
    async def validate_connection(self, session_id: str) -> bool:
        """Validate that the data source for a session is accessible."""
        try:
            source = self.source_manager.get_session_source(session_id)
            if not source:
                return False
            
            if source.type == DataSourceType.UPLOADED_FILE:
                conn = source.get_connection()
                # Simple test query
                conn.execute("SELECT 1").fetchone()
                return True
            elif source.type == DataSourceType.DEFAULT_POSTGRES:
                # Test PostgreSQL connection
                await self.postgres_executor.execute_query("SELECT 1")
                return True
                
            return False
            
        except Exception as e:
            logger.error("connection_validation_failed", 
                        session_id=session_id, 
                        error=str(e))
            return False