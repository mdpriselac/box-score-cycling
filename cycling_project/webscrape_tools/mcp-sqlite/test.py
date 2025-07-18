#!/usr/bin/env python3
import sqlite3
import os

# Create a test database
db_path = "test.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create a test table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE
    )
''')

# Insert test data
cursor.execute("INSERT OR REPLACE INTO users (name, email) VALUES (?, ?)", ("Alice", "alice@example.com"))
cursor.execute("INSERT OR REPLACE INTO users (name, email) VALUES (?, ?)", ("Bob", "bob@example.com"))
conn.commit()
conn.close()

print(f"Test database created at: {os.path.abspath(db_path)}")
print("\nTest queries to try with the MCP tool:")
print("1. SELECT * FROM users")
print("2. SELECT name FROM users WHERE id = 1")
print("3. INSERT INTO users (name, email) VALUES ('Charlie', 'charlie@example.com')")
print("4. UPDATE users SET email = 'alice2@example.com' WHERE name = 'Alice'")
print("5. DELETE FROM users WHERE name = 'Bob'")