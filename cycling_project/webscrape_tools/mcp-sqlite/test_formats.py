#!/usr/bin/env python3
import subprocess
import json
import sys

# Create a test database with sample data
import sqlite3

print("Creating test database with sample data...")
conn = sqlite3.connect('format_test.db')
cursor = conn.cursor()

# Create and populate a test table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        price REAL,
        in_stock INTEGER
    )
''')

# Insert sample data
products = [
    ('Laptop Pro 15"', 'Electronics', 1299.99, 15),
    ('Wireless Mouse', 'Electronics', 29.99, 250),
    ('Standing Desk', 'Furniture', 399.99, 8),
    ('Office Chair', 'Furniture', 249.99, 12),
    ('USB-C Cable', 'Electronics', 19.99, 500),
    ('Monitor 27"', 'Electronics', 349.99, 22),
    ('Desk Lamp', 'Furniture', 49.99, 45),
    ('Keyboard Mechanical', 'Electronics', 129.99, 38),
    ('Webcam HD', 'Electronics', 79.99, 65),
    ('Notebook Set', 'Stationery', 24.99, 200)
]

cursor.execute('DELETE FROM products')  # Clear existing data
cursor.executemany('INSERT INTO products (name, category, price, in_stock) VALUES (?, ?, ?, ?)', products)
conn.commit()
conn.close()

print("\nDatabase created with 10 sample products.\n")
print("=" * 60)

# Test queries with different formats
test_cases = [
    {
        "description": "Table format (default) with limit 5",
        "query": {
            "query": "SELECT * FROM products",
            "format": "table",
            "limit": 5
        }
    },
    {
        "description": "JSON format with limit 3",
        "query": {
            "query": "SELECT name, price FROM products WHERE category = 'Electronics'",
            "format": "json",
            "limit": 3
        }
    },
    {
        "description": "Table format showing all rows (no automatic limit for non-SELECT)",
        "query": {
            "query": "SELECT COUNT(*) as total_products, AVG(price) as avg_price FROM products",
            "format": "table"
        }
    }
]

# Function to call the MCP server
def execute_mcp_query(query_params):
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "execute_query",
            "arguments": query_params
        },
        "id": 1
    }
    
    # This simulates what would happen when called through MCP
    # In reality, the MCP client would handle this communication
    print(f"Query: {query_params.get('query')}")
    print(f"Format: {query_params.get('format', 'table')}")
    print(f"Limit: {query_params.get('limit', 50)}")
    print()

# Run test cases
for i, test in enumerate(test_cases):
    print(f"{i+1}. {test['description']}")
    print("-" * 60)
    execute_mcp_query(test['query'])
    print("=" * 60)
    print()

print("\nKey differences between formats:")
print("- Table format: Human-readable, aligned columns, easy to scan")
print("- JSON format: Machine-readable, nested structure, better for programmatic use")
print("- Limit parameter: Automatically applied to SELECT queries to prevent overwhelming output")
print("- Default limit is 50 rows, max is 1000 rows")