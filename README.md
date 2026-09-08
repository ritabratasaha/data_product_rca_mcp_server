# MCP Server Template

A minimal Python MCP (Model Context Protocol) server template.

## Installation

```bash
pip install -e .
```

## Usage

Run the server:

```bash
mcp-server
```

### Cursor Integration

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "mcp-server"
    }
  }
}
```

## Adding New Tools

Edit `src/mcp_server/tools.py`:

1. Add tool definition to `TOOLS` dict
2. Add handler case in `handle_tool_call()`
3. Implement the handler function

## Project Structure

```
├── pyproject.toml
├── README.md
└── src/
    └── mcp_server/
        ├── __init__.py
        ├── main.py      # Server entry point
        └── tools.py     # Tool definitions
```
