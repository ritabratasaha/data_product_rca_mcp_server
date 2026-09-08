"""Ping tool for server health check."""

from datetime import datetime, timezone

from langfuse import observe

from lineage_server.langfuse_connection_manager import get_langfuse_status


@observe()
async def ping() -> dict:
    """
    Test if the MCP server is responding.

    Returns:
        A dict containing:
        - success: Whether the server is operational
        - message: A confirmation message
        - timestamp: Current server time (UTC)
        - tracing: Langfuse connection status
    """
    status = get_langfuse_status()
    return {
        "success": True,
        "message": "pong - lineage server is running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tracing": {
            "enabled": status["langfuse_available"],
            "error": status["langfuse_error"]
        }
    }
