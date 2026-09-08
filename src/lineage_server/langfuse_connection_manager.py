"""Langfuse connection manager with health checking."""

import os
from langfuse import get_client
from lineage_server.logger import get_logger

logger = get_logger("langfuse_connection_manager")

_langfuse_available: bool = False
_langfuse_error: str | None = None


def init_langfuse() -> bool:
    """Initialize and verify Langfuse connection at startup."""
    global _langfuse_available, _langfuse_error
    
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    if not public_key or public_key.startswith("pk-lf-placeholder"):
        _langfuse_available = False
        _langfuse_error = "Langfuse credentials not configured"
        logger.warning(_langfuse_error)
        return False
    
    try:
        langfuse = get_client()
        langfuse.auth_check()  # Verify connection
        _langfuse_available = True
        _langfuse_error = None
        logger.info("Langfuse Cloud connection verified")
        return True
    except Exception as e:
        _langfuse_available = False
        _langfuse_error = str(e)
        logger.error(f"Langfuse connection failed: {e}")
        return False


def is_langfuse_available() -> bool:
    """Check if Langfuse is available."""
    return _langfuse_available


def get_langfuse_status() -> dict:
    """Get Langfuse connection status for tool responses."""
    return {
        "langfuse_available": _langfuse_available,
        "langfuse_error": _langfuse_error
    }
