"""API routes for schema extraction and visualization."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime

import structlog

from sens.datasource import DataSourceManager
from sens.api.routers.datasource import get_datasource_manager
from sens.schema.unified_schema import UnifiedSchema, TableInfo as UnifiedTableInfo

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/schema", tags=["schema"])


class SchemaAttribute(BaseModel):
    """Schema attribute for frontend visualization."""
    id: str
    name: str
    dataType: str
    semanticType: Optional[str] = None
    constraints: Dict[str, Any] = {}
    metadata: Optional[Dict[str, Any]] = None


class SchemaEntity(BaseModel):
    """Schema entity (table) for frontend visualization."""
    id: str
    name: str
    type: str = "table"
    category: Optional[str] = None
    displayName: Optional[str] = None
    description: Optional[str] = None
    attributes: List[SchemaAttribute]
    stats: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    isPartitioned: bool = False
    partitionInfo: Optional[Dict[str, Any]] = None


class SchemaRelationship(BaseModel):
    """Schema relationship for frontend visualization."""
    id: str
    source: str
    target: str
    type: str
    sourceAttribute: str
    targetAttribute: str
    label: Optional[str] = None


class UniversalSchemaResponse(BaseModel):
    """Schema response format for frontend visualization."""
    source: Dict[str, Any]
    entities: List[SchemaEntity]
    relationships: List[SchemaRelationship]
    categories: Optional[Dict[str, List[str]]] = None
    metadata: Dict[str, Any]


def map_data_type_to_semantic(data_type: str, column_name: str) -> Optional[str]:
    """Map data type and column name to semantic type."""
    # Date/time types
    if any(t in data_type.lower() for t in ['date', 'time', 'timestamp']):
        return 'date'
    
    # Money/currency
    if any(word in column_name.lower() for word in ['price', 'cost', 'amount', 'value', 'fee', 'revenue', 'salary']):
        if any(t in data_type.lower() for t in ['decimal', 'numeric', 'float', 'double']):
            return 'money'
    
    # Percentage
    if any(word in column_name.lower() for word in ['percent', 'pct', 'rate', 'ratio']):
        return 'percentage'
    
    # Quantity
    if any(word in column_name.lower() for word in ['count', 'quantity', 'qty', 'volume', 'size']):
        if any(t in data_type.lower() for t in ['int', 'bigint', 'numeric']):
            return 'quantity'
    
    # Identifier
    if column_name.lower().endswith('_id') or column_name.lower() == 'id':
        return 'id'
    
    # Boolean
    if 'bool' in data_type.lower():
        return 'boolean'
    
    # JSON
    if 'json' in data_type.lower():
        return 'json'
    
    # Text
    if any(t in data_type.lower() for t in ['varchar', 'char', 'text', 'string']):
        return 'text'
    
    return None


def categorize_table(table_name: str, schema: UnifiedSchema) -> Optional[str]:
    """Categorize a table based on its name and content."""
    name_lower = table_name.lower()
    
    # Financial/Market data patterns
    if any(word in name_lower for word in ['price', 'quote', 'trade', 'market', 'tick', 'ohlc', 'bar']):
        return 'Market Data'
    
    # Reference/Master data
    if any(word in name_lower for word in ['security', 'securities', 'symbol', 'company', 'exchange', 
                                          'sector', 'industry', 'currency', 'country', 'region']):
        return 'Reference Data'
    
    # Analytics/Derived data
    if any(word in name_lower for word in ['portfolio', 'position', 'holding', 'performance', 
                                          'return', 'risk', 'analytics', 'report', 'summary']):
        return 'Analytics'
    
    # Economic/Macro data
    if any(word in name_lower for word in ['economic', 'indicator', 'gdp', 'inflation', 'unemployment']):
        return 'Economic Data'
    
    # System/Meta tables
    if any(word in name_lower for word in ['user', 'log', 'audit', 'config', 'setting', 'meta']):
        return 'System'
    
    # Default based on content analysis
    # Check if it's a fact table (has foreign keys)
    table_info = next((t for t in schema.tables if t.name == table_name), None)
    if table_info:
        fk_count = sum(1 for col in table_info.columns if col.is_foreign_key)
        if fk_count >= 2:
            return 'Fact Tables'
        elif fk_count == 0 and len(table_info.columns) < 10:
            return 'Dimension Tables'
    
    return 'Other'


@router.get("/visualize", response_model=UniversalSchemaResponse)
async def get_schema_for_visualization(
    session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
) -> UniversalSchemaResponse:
    """Get schema in a format suitable for frontend visualization."""
    
    # Get the appropriate data source
    if not session_id or session_id == "default":
        # Ensure default database schema is extracted
        await datasource_manager.ensure_default_schema_extracted()
        source = datasource_manager.get_source("default")
        if not source:
            raise HTTPException(status_code=404, detail="Default database not available")
    else:
        source = datasource_manager.get_session_source(session_id)
        if not source:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Extract schema if not already done
    if not source.unified_schema:
        await datasource_manager._extract_schema(source)
    
    schema = source.unified_schema
    
    # Convert to frontend format
    entities = []
    relationships = []
    categories = {}
    
    # Process tables
    for table in schema.tables:
        # Map columns to attributes
        attributes = []
        for col in table.columns:
            attr = SchemaAttribute(
                id=f"{table.name}_{col.name}",
                name=col.name,
                dataType=col.data_type.value,
                semanticType=map_data_type_to_semantic(col.data_type.value, col.name),
                constraints={
                    "primaryKey": col.is_primary_key,
                    "foreignKey": {"entity": col.foreign_key_table, "attribute": col.foreign_key_column} if col.is_foreign_key else None,
                    "unique": getattr(col, 'is_unique', False),
                    "nullable": col.is_nullable
                }
            )
            
            # Add metadata for specific types
            if attr.semanticType == 'money':
                attr.metadata = {"unit": "USD"}  # Default currency
            elif attr.semanticType == 'percentage':
                attr.metadata = {"unit": "%"}
            
            attributes.append(attr)
        
        # Determine category
        category = categorize_table(table.name, schema)
        
        # Check if partitioned
        is_partitioned = any(word in table.name.lower() for word in ['_y', '_m', '_q', '_partition'])
        
        # Create entity
        entity = SchemaEntity(
            id=table.name,
            name=table.name,
            type="table",
            category=category,
            displayName=table.name.replace('_', ' ').title(),
            description=table.description,
            attributes=attributes,
            stats={
                "rowCount": table.row_count,
                "lastUpdated": datetime.utcnow()
            },
            isPartitioned=is_partitioned
        )
        
        entities.append(entity)
        
        # Track categories
        if category:
            if category not in categories:
                categories[category] = []
            categories[category].append(table.name)
        
        # Extract relationships from foreign keys
        for col in table.columns:
            if col.is_foreign_key and col.foreign_key_table:
                rel_id = f"rel_{table.name}_{col.name}"
                relationship = SchemaRelationship(
                    id=rel_id,
                    source=table.name,
                    target=col.foreign_key_table,
                    type="many-to-one",
                    sourceAttribute=col.name,
                    targetAttribute=col.foreign_key_column or "id",
                    label=col.name.replace('_id', '').replace('_', ' ')
                )
                relationships.append(relationship)
    
    # Build response
    response = UniversalSchemaResponse(
        source={
            "type": source.type.value.lower().replace('_', ''),
            "name": source.name,
            "version": getattr(schema, 'db_version', 'unknown')
        },
        entities=entities,
        relationships=relationships,
        categories=categories if categories else None,
        metadata={
            "extractedAt": datetime.utcnow(),
            "totalTables": len(entities),
            "totalColumns": sum(len(e.attributes) for e in entities),
            "totalRelationships": len(relationships)
        }
    )
    
    return response


@router.post("/refresh")
async def refresh_schema(
    session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
):
    """Force refresh schema extraction for a data source."""
    
    # Get the appropriate data source
    if not session_id or session_id == "default":
        source = datasource_manager.get_source("default")
        if not source:
            raise HTTPException(status_code=404, detail="Default database not available")
    else:
        source = datasource_manager.get_session_source(session_id)
        if not source:
            raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # Force re-extraction
        source.schema_extracted = False
        source.unified_schema = None
        await datasource_manager._extract_schema(source)
        
        return {
            "message": "Schema refreshed successfully",
            "source_id": source.id,
            "source_name": source.name
        }
    except Exception as e:
        logger.error("schema_refresh_failed", 
                    source_id=source.id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to refresh schema: {str(e)}")