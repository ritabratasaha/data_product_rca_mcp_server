"""Langfuse connection manager with health checking."""

import os
from langfuse import get_client
from rca_server.logger import get_logger

logger = get_logger("langfuse_connection_manager")

# Module-level state for Langfuse connection
langfuse_available: bool = False
langfuse_error: str | None = None


def init_langfuse() -> bool:
    """Initialize and verify Langfuse connection at startup."""
    global langfuse_available, langfuse_error
    
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    if not public_key or public_key.startswith("pk-lf-placeholder"):
        langfuse_available = False
        langfuse_error = "Langfuse credentials not configured"
        logger.warning(langfuse_error)
        return False
    
    try:
        langfuse = get_client()
        langfuse.auth_check()  # Verify connection
        langfuse_available = True
        langfuse_error = None
        logger.info("Langfuse Cloud connection verified")
        return True
    except Exception as e:
        langfuse_available = False
        langfuse_error = str(e)
        logger.error(f"Langfuse connection failed: {e}")
        return False


def get_langfuse_status() -> dict:
    """Get Langfuse connection status for tool responses."""
    return {
        "langfuse_available": langfuse_available,
        "langfuse_error": langfuse_error
    }
