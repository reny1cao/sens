"""Dynamic query suggestion generation based on uploaded data schema."""

import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from collections import Counter
import re

if TYPE_CHECKING:
    from sens.schema.unified_schema import UnifiedSchema, DataType

logger = logging.getLogger(__name__)


class QuerySuggestionGenerator:
    """Generates contextual query suggestions based on data schema and content."""
    
    def __init__(self):
        # Import DataType for comparison
        from sens.schema.unified_schema import DataType
        
        self.numeric_types = {
            DataType.INTEGER, DataType.BIGINT, DataType.SMALLINT,
            DataType.NUMERIC, DataType.DECIMAL, DataType.FLOAT, DataType.DOUBLE
        }
        self.text_types = {DataType.TEXT, DataType.VARCHAR, DataType.CHAR}
        self.date_types = {DataType.DATE, DataType.TIME, DataType.TIMESTAMP, DataType.TIMESTAMPTZ}
        self.boolean_types = {DataType.BOOLEAN}
    
    def generate_suggestions(self, unified_schema: 'UnifiedSchema', sample_data: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """Generate query suggestions based on unified schema and optional sample data.
        
        Args:
            unified_schema: UnifiedSchema object containing schema information
            sample_data: Optional sample rows for more intelligent suggestions
            
        Returns:
            List of suggested natural language queries
        """
        suggestions = []
        
        # Get table information
        tables = unified_schema.tables
        
        for table in tables:
            table_name = table.name
            columns = table.columns
            
            # Basic count query
            suggestions.append(f"How many {self._pluralize(table_name)} are there?")
            suggestions.append(f"Count all {table_name} records")
            
            # Analyze columns for specific suggestions
            numeric_columns = []
            text_columns = []
            date_columns = []
            boolean_columns = []
            
            for col in columns:
                col_name = col.name
                col_type = col.data_type
                
                if col_type in self.numeric_types:
                    numeric_columns.append(col_name)
                elif col_type in self.text_types:
                    text_columns.append(col_name)
                elif col_type in self.date_types:
                    date_columns.append(col_name)
                elif col_type in self.boolean_types:
                    boolean_columns.append(col_name)
            
            # Numeric column suggestions
            for col in numeric_columns:
                readable_col = self._make_readable(col)
                suggestions.extend([
                    f"What is the average {readable_col}?",
                    f"What is the total {readable_col}?",
                    f"What is the maximum {readable_col}?",
                    f"What is the minimum {readable_col}?",
                    f"Show the distribution of {readable_col}",
                    f"Find {table_name} with {readable_col} greater than average"
                ])
                
                # If we have sample data, add value-based suggestions
                if sample_data and col in sample_data[0]:
                    sample_values = [row.get(col) for row in sample_data[:10] if row.get(col) is not None]
                    if sample_values:
                        avg_val = sum(sample_values) / len(sample_values)
                        suggestions.append(f"Show all {table_name} with {readable_col} above {int(avg_val)}")
            
            # Text column suggestions
            for col in text_columns:
                readable_col = self._make_readable(col)
                suggestions.extend([
                    f"Show all unique {readable_col} values",
                    f"Count {table_name} by {readable_col}",
                    f"What are the most common {readable_col} values?",
                    f"Find {table_name} where {readable_col} contains specific text"
                ])
                
                # If we have sample data, add specific value suggestions
                if sample_data and col in sample_data[0]:
                    sample_values = [row.get(col) for row in sample_data[:20] if row.get(col)]
                    if sample_values:
                        # Find most common values
                        value_counts = Counter(sample_values)
                        common_values = value_counts.most_common(3)
                        for value, _ in common_values:
                            if value and len(str(value)) < 50:  # Avoid very long values
                                suggestions.append(f"Show all {table_name} where {readable_col} is '{value}'")
            
            # Date column suggestions
            for col in date_columns:
                readable_col = self._make_readable(col)
                suggestions.extend([
                    f"Show {table_name} from the last 30 days",
                    f"Group {table_name} by {readable_col} (monthly)",
                    f"What is the earliest {readable_col}?",
                    f"What is the latest {readable_col}?",
                    f"Show {table_name} between two dates"
                ])
            
            # Boolean column suggestions
            for col in boolean_columns:
                readable_col = self._make_readable(col)
                suggestions.extend([
                    f"How many {table_name} have {readable_col} as true?",
                    f"Show all {table_name} where {readable_col} is false",
                    f"What percentage of {table_name} have {readable_col} set?"
                ])
            
            # Combination queries
            if numeric_columns and text_columns:
                num_col = numeric_columns[0]
                text_col = text_columns[0]
                suggestions.extend([
                    f"What is the average {self._make_readable(num_col)} by {self._make_readable(text_col)}?",
                    f"Show top 10 {self._make_readable(text_col)} by {self._make_readable(num_col)}",
                    f"Compare {self._make_readable(num_col)} across different {self._make_readable(text_col)} values"
                ])
            
            # Top N queries
            if numeric_columns:
                for col in numeric_columns[:2]:  # Limit to avoid too many suggestions
                    readable_col = self._make_readable(col)
                    suggestions.extend([
                        f"Show top 10 {table_name} by {readable_col}",
                        f"Show bottom 5 {table_name} by {readable_col}"
                    ])
            
            # General analytical queries
            suggestions.extend([
                f"Show a summary of {table_name} data",
                f"What are the key statistics for {table_name}?",
                f"Show recent {table_name} entries"
            ])
        
        # Multi-table queries if there are relationships
        if len(tables) > 1:
            suggestions.extend([
                "Show data from all tables",
                "How are the tables related?",
                "Combine data from multiple tables"
            ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)
        
        # Limit to reasonable number of suggestions
        return unique_suggestions[:30]
    
    def _make_readable(self, column_name: str) -> str:
        """Convert column name to readable format.
        
        Examples:
            user_id -> user ID
            firstName -> first name
            total_amount -> total amount
        """
        # Handle camelCase
        result = re.sub('([a-z])([A-Z])', r'\1 \2', column_name)
        # Handle snake_case
        result = result.replace('_', ' ')
        # Handle common abbreviations
        result = result.replace(' id', ' ID')
        result = result.replace(' url', ' URL')
        result = result.replace(' api', ' API')
        # Lowercase everything except acronyms
        words = result.split()
        readable_words = []
        for word in words:
            if word.isupper() and len(word) > 1:
                readable_words.append(word)
            else:
                readable_words.append(word.lower())
        return ' '.join(readable_words)
    
    def _pluralize(self, word: str) -> str:
        """Simple pluralization for table names."""
        word = word.lower()
        if word.endswith('y') and word[-2] not in 'aeiou':
            return word[:-1] + 'ies'
        elif word.endswith(('s', 'x', 'z', 'ch', 'sh')):
            return word + 'es'
        else:
            return word + 's'
    
    def generate_contextual_suggestions(self, unified_schema: 'UnifiedSchema', column: str, value: Any) -> List[str]:
        """Generate suggestions based on a specific column and value context.
        
        Args:
            unified_schema: UnifiedSchema object
            column: Column name
            value: Sample value from that column
            
        Returns:
            List of contextual suggestions
        """
        suggestions = []
        table_name = unified_schema.tables[0].name if unified_schema.tables else "table"  # Use first table name
        readable_col = self._make_readable(column)
        
        # Determine value type
        if isinstance(value, (int, float)):
            suggestions.extend([
                f"Show all records where {readable_col} is greater than {value}",
                f"Show all records where {readable_col} is less than {value}",
                f"How many records have {readable_col} equal to {value}?",
                f"What's the average {readable_col} compared to {value}?"
            ])
        elif isinstance(value, str):
            suggestions.extend([
                f"Show all records where {readable_col} is '{value}'",
                f"How many records have {readable_col} as '{value}'?",
                f"What other values exist for {readable_col}?",
                f"Show records where {readable_col} starts with '{value[:3]}'"
            ])
        elif isinstance(value, bool):
            suggestions.extend([
                f"Show all records where {readable_col} is {value}",
                f"What percentage of records have {readable_col} as {value}?",
                f"Compare records where {readable_col} is true vs false"
            ])
        
        return suggestions


def generate_query_suggestions(unified_schema: 'UnifiedSchema', sample_data: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Convenience function to generate query suggestions.
    
    Args:
        unified_schema: UnifiedSchema object containing schema
        sample_data: Optional sample data for better suggestions
        
    Returns:
        List of suggested queries
    """
    generator = QuerySuggestionGenerator()
    return generator.generate_suggestions(unified_schema, sample_data)