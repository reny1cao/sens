# Embedding-based Schema Search

This module implements semantic search over database schema components using sentence embeddings. It enables finding relevant tables and columns even when there are no exact token matches.

## Features

- **Semantic Column Search**: Find relevant columns based on semantic similarity using SBERT embeddings
- **Rich Column Representation**: Each column is represented as `"{table}.{column} – {humanized_name} – {description}"`
- **Fast Retrieval**: Uses FAISS HNSW index for efficient similarity search
- **Persistent Indices**: Saves and loads indices from disk for quick startup
- **Structured Logging**: All operations are logged with structured metadata

## Usage

### Python API

```python
from sens.embedding import top_columns

# Search for relevant columns
results = top_columns("user rating score", k=5)
for table, column, score in results:
    print(f"{table}.{column}: {score:.3f}")
```

### HTTP API

```bash
# Search for columns (returns top 20 by default)
curl "http://localhost:8000/embedding/search?query=user+rating+score"

# Specify number of results
curl "http://localhost:8000/embedding/search?query=user+rating+score&k=5"
```

## Implementation Details

### Model

- Uses the `all-MiniLM-L6-v2` model from sentence-transformers
- 384-dimensional embeddings
- Optimized for semantic similarity tasks

### Index

- FAISS HNSW index for approximate nearest neighbor search
- 32 neighbors per node for graph construction
- `efConstruction=200` for thorough index building
- Typical latency < 10ms for 10,000 columns

### File Structure

- `columns.index`: FAISS index file (binary)
- `lookup.npy`: NumPy array mapping indices to (table, column) pairs

## API Reference

### Python

- `top_columns(query: str, k: int = 20) -> List[Tuple[str, str, float]]`
  - Returns list of (table, column, score) tuples sorted by relevance

### HTTP

- `GET /embedding/search`
  - Query Parameters:
    - `query`: Search query string
    - `k`: Number of results (1-100, default: 20)
  - Returns: List of column matches with scores
