# SENS Retrieval System Modernization Plan - 2025

## Executive Summary

The current SENS retrieval system faces several critical issues:
1. **Python Environment Issue**: Missing `_ctypes` module prevents embedding index building
2. **Performance**: FAISS dependency creates installation complexity
3. **Wrong Schema Loading**: System defaults to example schema instead of financial database
4. **Outdated Architecture**: Using 2022-era embedding models and retrieval patterns

This document outlines a modern, production-ready retrieval architecture for 2025.

## Current State Analysis

### Issues Identified

1. **Embedding Index Building Failure**
   - Error: `No module named '_ctypes'`
   - Root cause: Python installation missing system dependencies
   - Impact: Cannot build or use embedding-based search

2. **Schema Mismatch**
   - System uses example schema (movie/tv_show) instead of financial database
   - Schema file is 22MB+ (too large for efficient loading)
   - No automatic schema detection for active database

3. **Outdated Technology Stack**
   - FAISS requires complex C++ dependencies
   - SentenceTransformers with MiniLM-L6-v2 (2021 model)
   - No support for modern embedding APIs
   - Synchronous search operations

4. **Architecture Limitations**
   - Tight coupling between retrieval and embedding generation
   - No fallback when embedding search fails
   - Cache-only redundancy (no persistent vector store)

## Modern Retrieval Architecture (2025)

### 1. Hybrid Search Strategy

```python
class ModernRetriever:
    """Multi-strategy retrieval with graceful degradation"""
    
    def __init__(self):
        self.strategies = [
            KeywordStrategy(),      # BM25/TF-IDF
            SemanticStrategy(),     # Embeddings
            GraphStrategy(),        # Schema relationships
            StatisticalStrategy()   # Column cardinality/usage
        ]
    
    async def retrieve(self, query: str) -> RetrievalResult:
        results = await asyncio.gather(
            *[s.search(query) for s in self.strategies],
            return_exceptions=True
        )
        return self.fusion_ranker.merge(results)
```

### 2. Embedding System Redesign

#### Option A: Serverless Embeddings (Recommended)
```python
class ServerlessEmbeddings:
    """Use external embedding APIs - no local dependencies"""
    
    providers = {
        "openai": OpenAIEmbeddings(model="text-embedding-3-small"),
        "cohere": CohereEmbeddings(model="embed-english-v3.0"),
        "voyage": VoyageEmbeddings(model="voyage-2"),
        "local": OllamaEmbeddings(model="nomic-embed-text")
    }
    
    async def embed(self, texts: List[str]) -> np.ndarray:
        # Try providers in order until one succeeds
        for provider in self.providers.values():
            try:
                return await provider.embed_documents(texts)
            except Exception as e:
                continue
        # Fallback to keyword-only search
        return None
```

#### Option B: Lightweight Local Embeddings
```python
class LightweightEmbeddings:
    """Use pure Python embedding solutions"""
    
    def __init__(self):
        # Use ONNX Runtime instead of PyTorch
        self.model = ONNXModel("all-MiniLM-L6-v2.onnx")
        # Or use TF-IDF as embedding
        self.tfidf = TfidfVectorizer(max_features=384)
    
    def embed(self, texts: List[str]) -> np.ndarray:
        # No C dependencies required
        return self.model.encode(texts)
```

### 3. Vector Store Alternatives

#### Replace FAISS with Modern Solutions

```python
class VectorStoreFactory:
    """Factory for vector store backends"""
    
    @staticmethod
    def create(config: Config) -> VectorStore:
        if config.vector_store == "chroma":
            # Pure Python, embedded database
            return ChromaDB(persist_directory="./chroma_db")
        
        elif config.vector_store == "qdrant":
            # Rust-based, can run embedded
            return Qdrant(path="./qdrant_db")
        
        elif config.vector_store == "lance":
            # Modern columnar format
            return LanceDB(uri="./lance_db")
        
        elif config.vector_store == "sqlite-vec":
            # SQLite extension for vectors
            return SQLiteVec(db_path="./vectors.db")
        
        elif config.vector_store == "numpy":
            # Pure NumPy for small datasets
            return NumpyVectorStore(index_path="./numpy_index.npz")
```

### 4. Schema Management Improvements

```python
class SchemaManager:
    """Intelligent schema detection and caching"""
    
    def __init__(self):
        self.cache = DiskCache("./schema_cache")
        self.active_schema = None
    
    async def get_active_schema(self) -> Schema:
        # 1. Check which database is active
        db_url = get_settings().database_url
        schema_key = hashlib.md5(db_url.encode()).hexdigest()
        
        # 2. Use cached schema if fresh
        if cached := self.cache.get(schema_key):
            if cached.age < timedelta(hours=24):
                return cached.schema
        
        # 3. Extract only essential schema info
        essential_schema = await self.extract_essential_schema()
        
        # 4. Cache the result
        self.cache.set(schema_key, essential_schema)
        
        return essential_schema
    
    async def extract_essential_schema(self) -> Schema:
        """Extract only what's needed for retrieval"""
        # Don't load 22MB of data!
        return Schema(
            tables=await self.get_table_list(),
            columns=await self.get_column_list(),
            relationships=await self.get_relationships(),
            statistics=await self.get_column_statistics()
        )
```

### 5. Intelligent Retrieval Pipeline

```python
class IntelligentRetriever:
    """Modern retrieval with multiple strategies"""
    
    async def retrieve(self, query: str) -> RetrievalResult:
        # 1. Query Understanding
        intent = await self.understand_query(query)
        
        # 2. Strategy Selection
        strategies = self.select_strategies(intent)
        
        # 3. Parallel Retrieval
        results = await asyncio.gather(*[
            s.retrieve(query, intent) for s in strategies
        ])
        
        # 4. Result Fusion
        fused = self.fuse_results(results, intent)
        
        # 5. Re-ranking with Cross-Encoder
        if self.has_cross_encoder:
            fused = await self.cross_encoder_rerank(query, fused)
        
        # 6. Schema Expansion
        expanded = self.expand_with_relationships(fused)
        
        return expanded
```

## Implementation Plan

### Phase 1: Fix Immediate Issues (Week 1)

1. **Fix Schema Loading**
```python
# Quick fix in retrieval/orchestrator.py
class RetrievalOrchestrator:
    def __init__(self, ...):
        # Force financial schema
        self.schema = SchemaLoader.load_financial_schema()
```

2. **Add Fallback for Embeddings**
```python
# Add keyword-only fallback
class EmbeddingSearch:
    async def search(self, query: str, k: int = 20):
        try:
            return await self._embedding_search(query, k)
        except Exception as e:
            logger.warning(f"Embedding search failed: {e}")
            return self._keyword_fallback(query, k)
```

3. **Create Lightweight Index Builder**
```python
# New script: scripts/build_keyword_index.py
"""Build keyword index without embeddings"""
def build_keyword_index():
    schema = load_schema()
    index = KeywordIndex()
    
    for table in schema.tables:
        for column in table.columns:
            index.add(f"{table.name}.{column.name}", {
                "table": table.name,
                "column": column.name,
                "tokens": tokenize(column.name)
            })
    
    index.save("./indices/keyword_index.json")
```

### Phase 2: Modern Architecture (Week 2-3)

1. **Implement Serverless Embeddings**
   - Add OpenAI/Cohere embedding providers
   - Implement retry and fallback logic
   - Add cost tracking

2. **Replace FAISS with ChromaDB**
   - Pure Python implementation
   - Persistent storage
   - Built-in embedding support

3. **Add Query Understanding**
   - Detect query types (lookup, aggregation, join)
   - Extract key entities
   - Identify target tables/columns

### Phase 3: Advanced Features (Week 4+)

1. **Implement Cross-Encoder Re-ranking**
   - Use lightweight models
   - Cache re-ranking results
   - A/B test effectiveness

2. **Add Learning Component**
   - Track successful queries
   - Learn query patterns
   - Improve ranking over time

3. **Build Performance Monitoring**
   - Track retrieval latency
   - Monitor strategy effectiveness
   - Measure retrieval quality

## Migration Strategy

### Step 1: Parallel Implementation
- Keep existing system running
- Implement new system alongside
- Route 10% traffic to new system

### Step 2: Gradual Rollout
- Monitor quality metrics
- Increase traffic percentage
- Fix issues as they arise

### Step 3: Full Migration
- Switch all traffic to new system
- Keep old system as fallback
- Remove after 30 days stable

## Technology Recommendations

### Embedding Models (2025)
1. **OpenAI text-embedding-3-small**: Best quality/cost ratio
2. **Cohere embed-english-v3.0**: Good multilingual support
3. **Voyage voyage-2**: Optimized for code/technical content
4. **Local: BGE-M3**: Best open-source option

### Vector Stores
1. **ChromaDB**: Best for getting started quickly
2. **Qdrant**: Best performance and features
3. **LanceDB**: Best for analytical workloads
4. **SQLite-vec**: Best for simple deployments

### Retrieval Strategies
1. **BM25**: Still excellent for keyword matching
2. **ColBERT**: Best quality but resource intensive
3. **SPLADE**: Good balance of quality and efficiency
4. **Hybrid**: Combine multiple strategies

## Quick Wins

1. **Immediate Fix for _ctypes Error**
```bash
# Install system dependencies
sudo apt-get install python3-dev libffi-dev

# Or use conda environment
conda create -n sens python=3.11
conda activate sens
conda install -c conda-forge faiss-cpu
```

2. **Force Correct Schema**
```python
# In schema/graph.py
DEFAULT_SCHEMA_PATH = str(Path(__file__).parent / "financial_schema.json")
```

3. **Add Simple Keyword Search**
```python
# New file: retrieval/keyword_search.py
class KeywordSearch:
    def search(self, query: str, schema: Schema) -> List[Match]:
        tokens = query.lower().split()
        matches = []
        
        for table in schema.tables:
            for column in table.columns:
                score = self._score_match(tokens, column.name)
                if score > 0:
                    matches.append(Match(table.name, column.name, score))
        
        return sorted(matches, key=lambda x: x.score, reverse=True)
```

## Conclusion

The current retrieval system needs modernization to handle 2025 requirements:
- Remove C++ dependencies
- Use modern embedding APIs
- Implement multiple retrieval strategies
- Add proper fallbacks and error handling

This plan provides both immediate fixes and a path to a modern, production-ready system.