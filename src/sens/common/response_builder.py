"""
Standardized response building utilities.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..api.models.common import ErrorResponse, QueryMetadata, SuccessResponse
from ..api.models.nl2sql import NL2SQLResponse, SQLResult


class ResponseBuilder:
    """Builder for consistent API responses."""

    @staticmethod
    def build_success(
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a standard success response."""
        response = {
            "success": True,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if metadata:
            response["metadata"] = metadata

        if message:
            response["message"] = message

        return response

    @staticmethod
    def build_error(
        error: str,
        code: str = "ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ) -> Dict[str, Any]:
        """Build a standard error response."""
        return {
            "success": False,
            "error": error,
            "code": code,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def build_nl2sql_response(
        sql: str,
        results: Optional[List[Dict[str, Any]]] = None,
        column_names: Optional[List[str]] = None,
        metadata: Optional[QueryMetadata] = None,
        session_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> NL2SQLResponse:
        """Build a standardized NL2SQL response."""
        sql_result = None
        if results is not None and column_names is not None:
            # Convert dict results to list format
            rows = []
            for row in results:
                rows.append([row.get(col) for col in column_names])

            sql_result = SQLResult(
                column_names=column_names, rows=rows, row_count=len(rows)
            )

        return NL2SQLResponse(
            success=error is None,
            sql=sql,
            results=sql_result,
            error=error,
            session_id=session_id,
            metadata=metadata,
        )


def format_sql_results(
    results: List[Dict[str, Any]], column_names: Optional[List[str]] = None
) -> SQLResult:
    """Convert query results to standard format."""
    if not results:
        return SQLResult(column_names=column_names or [], rows=[], row_count=0)

    # Extract column names from first result if not provided
    if column_names is None:
        column_names = list(results[0].keys())

    # Convert to row format
    rows = []
    for result in results:
        row = [result.get(col) for col in column_names]
        rows.append(row)

    return SQLResult(column_names=column_names, rows=rows, row_count=len(rows))


def build_error_response(
    error: Exception, request_id: Optional[str] = None
) -> ErrorResponse:
    """Convert exception to error response."""
    from .errors import error_handler

    return error_handler.handle_error(error, request_id)


def build_success_response(
    data: Any, metadata: Optional[Dict[str, Any]] = None
) -> SuccessResponse:
    """Build a success response wrapper."""
    return SuccessResponse(data=data, metadata=metadata)
