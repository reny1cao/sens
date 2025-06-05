# Schema Context Enhancement

The schema context system provides rich metadata about database tables and their relationships to improve SQL generation accuracy.

## Sticky Columns

Sticky columns are high-value identifier columns that are automatically detected and prioritized in schema context. These columns typically represent the most semantically meaningful identifiers for their tables (e.g., `title` for movies, `name` for users).

### How It Works

The `IdentifierScorer` analyzes columns based on several factors:

1. **Name Patterns** (+3.0 points each):
   - Matches common identifier patterns (name, title, label)
   - Matches display-related patterns
   - Matches description fields

2. **Description Keywords** (+2.0 points each):
   - "identifier"
   - "display"
   - "primary"
   - "name"
   - "title"
   - "label"
   - "description"

3. **Data Type Bonus** (+2.0 points):
   - String-like types (varchar, text, char)

4. **Penalties**:
   - System fields (-3.0 points): created_at, updated_at, etc.
   - Foreign keys (-2.0 points): typically technical references
   - Numeric primary keys (-1.0 points): typically internal IDs

### Integration

Sticky columns are automatically:
1. Identified during schema retrieval
2. Included in the schema context
3. Formatted for LLM consumption with clear markers

### Example

```sql
TABLE movies (id, title, release_date, genre_id, created_at)
-- title: The main title of the movie
-- Primary identifiers: title

TABLE genres (id, name, description)
-- name: Genre classification name
-- Primary identifiers: name
```

### Benefits

1. **Better Context**: LLMs get clear signals about which columns are most meaningful for display and identification.
2. **Improved Joins**: Helps identify natural join conditions using semantic identifiers.
3. **Better Results**: Output includes meaningful identifiers instead of technical IDs.

### Configuration

The scoring system is configurable through the `IdentifierScorer` class:
- Patterns and keywords can be modified
- Scoring weights can be adjusted
- New heuristics can be added

## Usage

The feature is automatically integrated into the schema retrieval process:

```python
from sens.retrieval import SchemaRetriever

retriever = SchemaRetriever(schema_graph)
context = retriever.retrieve_schema_context("Show me movie titles")

# Access sticky columns
sticky_columns = context.sticky_columns
# {'movies': ['title'], 'genres': ['name']}
```

## Retrieval Output Format

When retrieving schema context with sticky columns, the output is formatted in a clear, LLM-friendly way. Here's how it looks for different queries:

### Movie-Related Query Example
For a query like "Show me movie titles and their release dates":

```sql
TABLE movies (id, title, release_date, genre_id, created_at)
-- title: The main title of the movie
-- release_date: When the movie was released
-- Primary identifiers: title

TABLE genres (id, name, description)
-- name: Genre classification name
-- Primary identifiers: name
```

### User-Related Query Example
For a query like "Find users and their profile information":

```sql
TABLE users (id, username, display_name, email, created_at)
-- username: User's login identifier
-- display_name: User's public display name
-- email: User's email address
-- Primary identifiers: username, display_name

TABLE profiles (id, user_id, bio, avatar_url)
-- bio: User's biography
-- avatar_url: URL to user's profile picture
-- Primary identifiers: bio
```

The output format consistently includes:
1. Full table definitions with all relevant columns
2. Column descriptions when available
3. Clearly marked sticky columns as "Primary identifiers"
4. Related tables through foreign key relationships
5. All necessary context for the LLM to understand the schema structure

This format ensures that the LLM has both the technical schema information and semantic understanding of which columns are most meaningful for identification and display purposes.
