"""Tests for query suggestion generation."""

import pytest
from datetime import datetime

from sens.datasource.models import DataSource
from sens.datasource.query_suggestions import QuerySuggestionGenerator, generate_query_suggestions


class TestQuerySuggestionGenerator:
    """Test the QuerySuggestionGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create a generator instance."""
        return QuerySuggestionGenerator()
    
    @pytest.fixture
    def sales_datasource(self):
        """Create a sample sales datasource."""
        return DataSource(
            id="test-sales",
            name="sales_data",
            type="csv",
            schema={
                "sales": {
                    "columns": {
                        "order_id": {"type": "INTEGER", "nullable": False},
                        "customer_name": {"type": "VARCHAR(255)", "nullable": False},
                        "product_name": {"type": "TEXT", "nullable": False},
                        "quantity": {"type": "INTEGER", "nullable": False},
                        "unit_price": {"type": "DECIMAL(10,2)", "nullable": False},
                        "total_amount": {"type": "DECIMAL(10,2)", "nullable": False},
                        "order_date": {"type": "DATE", "nullable": False},
                        "is_premium": {"type": "BOOLEAN", "nullable": True},
                        "status": {"type": "VARCHAR(50)", "nullable": False}
                    }
                }
            },
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def sample_sales_data(self):
        """Create sample sales data."""
        return [
            {
                "order_id": 1,
                "customer_name": "John Doe",
                "product_name": "Laptop",
                "quantity": 2,
                "unit_price": 999.99,
                "total_amount": 1999.98,
                "order_date": "2024-01-15",
                "is_premium": True,
                "status": "completed"
            },
            {
                "order_id": 2,
                "customer_name": "Jane Smith",
                "product_name": "Mouse",
                "quantity": 5,
                "unit_price": 29.99,
                "total_amount": 149.95,
                "order_date": "2024-01-16",
                "is_premium": False,
                "status": "completed"
            },
            {
                "order_id": 3,
                "customer_name": "John Doe",
                "product_name": "Keyboard",
                "quantity": 1,
                "unit_price": 149.99,
                "total_amount": 149.99,
                "order_date": "2024-01-17",
                "is_premium": True,
                "status": "pending"
            }
        ]
    
    def test_basic_suggestions(self, generator, sales_datasource):
        """Test basic query suggestions without sample data."""
        suggestions = generator.generate_suggestions(sales_datasource)
        
        # Check for basic count queries
        assert "How many sales are there?" in suggestions
        assert "Count all sales records" in suggestions
        
        # Check for numeric column suggestions
        assert "What is the average quantity?" in suggestions
        assert "What is the total total amount?" in suggestions
        assert "What is the maximum unit price?" in suggestions
        
        # Check for text column suggestions
        assert "Show all unique customer name values" in suggestions
        assert "Count sales by status" in suggestions
        
        # Check for date column suggestions
        assert "Show sales from the last 30 days" in suggestions
        assert "What is the earliest order date?" in suggestions
        
        # Check for boolean column suggestions
        assert "How many sales have is premium as true?" in suggestions
    
    def test_suggestions_with_sample_data(self, generator, sales_datasource, sample_sales_data):
        """Test suggestions with sample data for more specific queries."""
        suggestions = generator.generate_suggestions(sales_datasource, sample_sales_data)
        
        # Should include value-based suggestions
        assert any("Show all sales where customer name is 'John Doe'" in s for s in suggestions)
        assert any("Show all sales where status is 'completed'" in s for s in suggestions)
        
        # Should have numeric threshold suggestions
        assert any("above" in s and "quantity" in s for s in suggestions)
    
    def test_make_readable(self, generator):
        """Test column name readability conversion."""
        assert generator._make_readable("user_id") == "user ID"
        assert generator._make_readable("firstName") == "first name"
        assert generator._make_readable("total_amount") == "total amount"
        assert generator._make_readable("api_key") == "API key"
        assert generator._make_readable("URLPath") == "URL path"
    
    def test_pluralize(self, generator):
        """Test simple pluralization."""
        assert generator._pluralize("user") == "users"
        assert generator._pluralize("company") == "companies"
        assert generator._pluralize("box") == "boxes"
        assert generator._pluralize("batch") == "batches"
        assert generator._pluralize("dish") == "dishes"
    
    def test_contextual_suggestions(self, generator, sales_datasource):
        """Test contextual suggestions based on specific column/value."""
        # Numeric value context
        numeric_suggestions = generator.generate_contextual_suggestions(
            sales_datasource, "quantity", 5
        )
        assert "Show all records where quantity is greater than 5" in numeric_suggestions
        assert "Show all records where quantity is less than 5" in numeric_suggestions
        
        # String value context
        string_suggestions = generator.generate_contextual_suggestions(
            sales_datasource, "customer_name", "John Doe"
        )
        assert "Show all records where customer name is 'John Doe'" in string_suggestions
        assert "How many records have customer name as 'John Doe'?" in string_suggestions
        
        # Boolean value context
        bool_suggestions = generator.generate_contextual_suggestions(
            sales_datasource, "is_premium", True
        )
        assert "Show all records where is premium is True" in bool_suggestions
        assert "What percentage of records have is premium as True?" in bool_suggestions
    
    def test_multi_table_suggestions(self, generator):
        """Test suggestions for multi-table schemas."""
        multi_table_ds = DataSource(
            id="test-multi",
            name="multi_table",
            type="sqlite",
            schema={
                "users": {
                    "columns": {
                        "user_id": {"type": "INTEGER"},
                        "name": {"type": "VARCHAR(255)"}
                    }
                },
                "orders": {
                    "columns": {
                        "order_id": {"type": "INTEGER"},
                        "user_id": {"type": "INTEGER"},
                        "amount": {"type": "DECIMAL(10,2)"}
                    }
                }
            },
            created_at=datetime.now()
        )
        
        suggestions = generator.generate_suggestions(multi_table_ds)
        
        # Should include multi-table queries
        assert "Show data from all tables" in suggestions
        assert "How are the tables related?" in suggestions
        assert "Combine data from multiple tables" in suggestions
    
    def test_combination_queries(self, generator, sales_datasource):
        """Test combination queries using multiple columns."""
        suggestions = generator.generate_suggestions(sales_datasource)
        
        # Should include queries combining numeric and text columns
        assert any("average" in s and "by" in s for s in suggestions)
        assert any("top 10" in s and "by" in s for s in suggestions)
    
    def test_suggestion_limit(self, generator, sales_datasource):
        """Test that suggestions are limited to reasonable number."""
        suggestions = generator.generate_suggestions(sales_datasource)
        
        # Should not exceed 30 suggestions
        assert len(suggestions) <= 30
        
        # Should have no duplicates
        assert len(suggestions) == len(set(suggestions))
    
    def test_convenience_function(self, sales_datasource, sample_sales_data):
        """Test the convenience function."""
        suggestions = generate_query_suggestions(sales_datasource, sample_sales_data)
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert all(isinstance(s, str) for s in suggestions)