"""Development endpoint for NL2SQL - with mock responses."""

import asyncio
import random
import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

# Router for development/testing
router = APIRouter(
    prefix="/nl2sql-dev",
    tags=["nl2sql-dev"],
)


class NL2SQLRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class NL2SQLResponse(BaseModel):
    sql: str
    results: dict
    metadata: dict
    error: Optional[dict] = None


# Mock responses for common queries
MOCK_RESPONSES = {
    "users": {
        "sql": "SELECT COUNT(*) as user_count FROM users",
        "results": {
            "columns": ["user_count"],
            "data": [{"user_count": random.randint(1000, 5000)}],
            "row_count": 1,
        },
        "query_type": "aggregate",
        "tables": ["users"],
    },
    "customers": {
        "sql": "SELECT customer_id, name, email, total_revenue FROM customers ORDER BY total_revenue DESC LIMIT 10",
        "results": {
            "columns": ["customer_id", "name", "email", "total_revenue"],
            "data": [
                {
                    "customer_id": i,
                    "name": f"Customer {i}",
                    "email": f"customer{i}@example.com",
                    "total_revenue": random.randint(10000, 100000),
                }
                for i in range(1, 11)
            ],
            "row_count": 10,
        },
        "query_type": "select",
        "tables": ["customers"],
    },
    "sales": {
        "sql": "SELECT DATE_FORMAT(order_date, '%Y-%m') as month, SUM(total_amount) as revenue FROM orders WHERE order_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH) GROUP BY month ORDER BY month",
        "results": {
            "columns": ["month", "revenue"],
            "data": [
                {
                    "month": f"2024-{str(i).zfill(2)}",
                    "revenue": random.randint(50000, 150000),
                }
                for i in range(1, 7)
            ],
            "row_count": 6,
        },
        "query_type": "aggregate",
        "tables": ["orders"],
    },
    "products": {
        "sql": "SELECT product_id, name, category, price, stock_quantity FROM products WHERE status = 'active'",
        "results": {
            "columns": ["product_id", "name", "category", "price", "stock_quantity"],
            "data": [
                {
                    "product_id": i,
                    "name": f"Product {i}",
                    "category": random.choice(
                        ["Electronics", "Clothing", "Home", "Sports"]
                    ),
                    "price": round(random.uniform(10, 500), 2),
                    "stock_quantity": random.randint(0, 1000),
                }
                for i in range(1, 21)
            ],
            "row_count": 20,
        },
        "query_type": "select",
        "tables": ["products"],
    },
}


@router.post("/", response_model=NL2SQLResponse)
async def nl2sql_dev(request: NL2SQLRequest):
    """Development endpoint that returns mock data for testing the UI."""
    # Simulate processing time
    await asyncio.sleep(random.uniform(0.5, 1.5))

    # Determine which mock to use based on keywords
    question_lower = request.question.lower()

    if "user" in question_lower:
        mock_key = "users"
    elif "customer" in question_lower or "revenue" in question_lower:
        mock_key = "customers"
    elif "sales" in question_lower or "month" in question_lower:
        mock_key = "sales"
    elif "product" in question_lower:
        mock_key = "products"
    else:
        # Default response
        mock_key = "users"

    mock = MOCK_RESPONSES[mock_key]

    # Add some randomness to the data
    results = mock["results"].copy()
    if mock_key == "users":
        results["data"][0]["user_count"] = random.randint(1000, 5000)

    # Determine visualizations
    suggested_visualizations = ["table"]
    if results["row_count"] == 1 and len(results["columns"]) == 1:
        suggested_visualizations = ["single_value"]
    elif any(
        "date" in col.lower() or "month" in col.lower() for col in results["columns"]
    ):
        suggested_visualizations.append("time_series")

    return NL2SQLResponse(
        sql=mock["sql"],
        results=results,
        metadata={
            "execution_time_ms": random.randint(50, 200),
            "tables_used": mock["tables"],
            "query_type": mock["query_type"],
            "suggested_visualizations": suggested_visualizations,
        },
    )
