# MCP SQLite Tool

A simple MCP (Model Context Protocol) server that allows LLMs to execute SQL queries on SQLite databases.

## Installation

```bash
cd mcp-sqlite
npm install
```

## Configuration

The database path must be specified when starting the server. The LLM will not have access to the database location.

### Method 1: Command line argument

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "node",
      "args": ["/path/to/mcp-sqlite/server.js", "/path/to/your/database.db"]
    }
  }
}
```

### Method 2: Environment variable

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "node",
      "args": ["/path/to/mcp-sqlite/server.js"],
      "env": {
        "SQLITE_DB_PATH": "/path/to/your/database.db"
      }
    }
  }
}
```

## Available Tool

The server provides one tool:

- **execute_query**: Execute SQL queries on the configured SQLite database
  - `query` (required): The SQL query to execute
  - `format` (optional): Output format - "table" (default) or "json"
  - `limit` (optional): Maximum rows to return (default: 50, max: 1000)

## Output Formats

### Table Format (Default)
Human-readable ASCII table with aligned columns - ideal for LLM comprehension:
```
id  name              category     price   in_stock
--  ----------------  -----------  ------  --------
1   Laptop Pro 15"    Electronics  1299.99  15     
2   Wireless Mouse    Electronics  29.99    250    
```

### JSON Format
Machine-readable JSON array - useful for structured data processing:
```json
[
  {"id": 1, "name": "Laptop Pro 15\"", "category": "Electronics", "price": 1299.99, "in_stock": 15},
  {"id": 2, "name": "Wireless Mouse", "category": "Electronics", "price": 29.99, "in_stock": 250}
]
```

## Examples

The LLM can execute queries without knowing the database location:

```javascript
// Simple query with default table format
execute_query({
  "query": "SELECT * FROM users"
})

// Query with JSON format and custom limit
execute_query({
  "query": "SELECT name, email FROM users WHERE active = 1",
  "format": "json",
  "limit": 20
})

// Preview large tables with limited rows
execute_query({
  "query": "SELECT * FROM logs ORDER BY created_at DESC",
  "format": "table",
  "limit": 10
})

// Insert data (no format needed for non-SELECT queries)
execute_query({
  "query": "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
})
```

**Note:** The `limit` parameter automatically adds a LIMIT clause to SELECT queries that don't already have one, preventing overwhelming output from large tables.

## Testing

Run the test script to create a sample database:

```bash
python3 test.py
```

This creates a `test.db` file with sample data you can query.