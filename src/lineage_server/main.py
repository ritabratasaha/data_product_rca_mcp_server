"""MCP server entry point."""

import os
import sys
from pathlib import Path


def _setup_path():
    """Add src/ to path for direct execution without pip install."""
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main():
    """Start the MCP server."""
    _setup_path()
    from lineage_server.logger import get_logger
    from lineage_server.tools import mcp

    logger = get_logger("main")

    transport = os.getenv("MCP_TRANSPORT", "http")  # Default to http for OAuth
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))

    logger.info(f"Starting MCP lineage server (transport={transport})...")

    if transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()

    logger.info("MCP lineage server stopped")


if __name__ == "__main__":
    main()
