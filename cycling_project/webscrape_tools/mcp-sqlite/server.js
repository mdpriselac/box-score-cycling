#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { 
  CallToolRequestSchema,
  ListToolsRequestSchema
} from '@modelcontextprotocol/sdk/types.js';
import { spawn } from 'child_process';

// Get database path from command line argument or environment variable
const dbPath = process.argv[2] || process.env.SQLITE_DB_PATH;

if (!dbPath) {
  console.error('Error: No database path specified.');
  console.error('Usage: node server.js <database-path>');
  console.error('Or set SQLITE_DB_PATH environment variable');
  process.exit(1);
}

const server = new Server(
  {
    name: 'sqlite-mcp',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Execute SQLite query using the sqlite3 command line tool
function executeSqlite(query, format = 'table', limit = 50) {
  return new Promise((resolve, reject) => {
    // Add LIMIT clause if not present and it's a SELECT query
    let limitedQuery = query.trim();
    // Remove trailing semicolon if present
    if (limitedQuery.endsWith(';')) {
      limitedQuery = limitedQuery.slice(0, -1).trim();
    }
    if (format === 'table' && 
        limitedQuery.toUpperCase().startsWith('SELECT') && 
        !limitedQuery.toUpperCase().includes('LIMIT')) {
      limitedQuery = `${limitedQuery} LIMIT ${limit}`;
    }
    
    // Choose sqlite3 output format
    const formatArgs = format === 'json' ? ['-json'] : ['-header', '-column'];
    const sqlite = spawn('sqlite3', [...formatArgs, dbPath, limitedQuery]);
    
    let stdout = '';
    let stderr = '';
    
    sqlite.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    sqlite.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    sqlite.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `SQLite process exited with code ${code}`));
      } else {
        if (format === 'json') {
          try {
            // Try to parse as JSON
            if (stdout.trim()) {
              const result = JSON.parse(stdout);
              resolve({ format: 'json', data: result });
            } else {
              resolve({ format: 'json', data: [], message: 'Query executed successfully' });
            }
          } catch (e) {
            resolve({ format: 'text', data: stdout.trim() || 'Query executed successfully' });
          }
        } else {
          // Return as formatted text table
          const output = stdout.trim() || 'Query executed successfully';
          const lines = output.split('\n');
          const rowCount = Math.max(0, lines.length - 2); // Subtract header and separator
          
          resolve({ 
            format: 'table', 
            data: output,
            rowCount: rowCount,
            limited: rowCount === limit
          });
        }
      }
    });
    
    sqlite.on('error', (err) => {
      reject(err);
    });
  });
}

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'execute_query',
      description: 'Execute a SQL query on the SQLite database',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'The SQL query to execute',
          },
          format: {
            type: 'string',
            description: 'Output format: "table" (default) for readable text table or "json" for JSON',
            enum: ['table', 'json'],
            default: 'table',
          },
          limit: {
            type: 'integer',
            description: 'Maximum number of rows to return (default: 50, max: 1000)',
            default: 50,
            minimum: 1,
            maximum: 1000,
          },
        },
        required: ['query'],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'execute_query') {
    const { query, format = 'table', limit = 50 } = request.params.arguments;
    
    try {
      const result = await executeSqlite(query, format, Math.min(limit, 1000));
      
      let outputText;
      if (result.format === 'table') {
        outputText = result.data;
        if (result.limited) {
          outputText += `\n\n[Results limited to ${limit} rows. Adjust 'limit' parameter or add LIMIT clause for more/fewer rows]`;
        }
      } else if (result.format === 'json') {
        outputText = JSON.stringify(result.data, null, 2);
      } else {
        outputText = result.data;
      }
      
      return {
        content: [
          {
            type: 'text',
            text: outputText,
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `Error: ${error.message}`,
          },
        ],
      };
    }
  }
  
  throw new Error(`Unknown tool: ${request.params.name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);