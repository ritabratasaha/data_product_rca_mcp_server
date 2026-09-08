"""Tool registry using FastMCP."""

import os

from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from observatory_sdk import instrument as prometheus_instrument
from langfuse import get_client

from lineage_server.logger import get_logger
from lineage_server.langfuse_connection_manager import init_langfuse, is_langfuse_available

logger = get_logger("registry")

# Google OAuth configuration (via environment variables)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000")

# Only initialize GoogleProvider if credentials are provided
auth = None
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    auth = GoogleProvider(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        base_url=SERVER_BASE_URL,
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
    )
    logger.info("Google OAuth configured")
else:
    logger.warning("Google OAuth credentials not provided, authentication disabled")

mcp = FastMCP("lineage-server")

# Prometheus metrics instrumentation (skip if TESTING env var is set)
if not os.getenv("TESTING"):
    prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))
    try:
        prometheus_instrument(mcp, service_name="lineage-server", prometheus_port=prometheus_port)
        logger.info(f"Prometheus metrics enabled on port {prometheus_port}")
    except OSError as e:
        logger.warning(f"Could not start Prometheus server: {e}")
else:
    logger.info("Prometheus metrics disabled for testing")

# Rate limiting configuration (configurable via env vars)
rate_limit_rps = float(os.getenv("RATE_LIMIT_RPS", "10.0"))
rate_limit_burst = int(os.getenv("RATE_LIMIT_BURST", "10"))

mcp.add_middleware(RateLimitingMiddleware(
    max_requests_per_second=rate_limit_rps,
    burst_capacity=rate_limit_burst
))
logger.info(f"Rate limiting enabled: {rate_limit_rps} req/sec, burst={rate_limit_burst}")

# Initialize Langfuse connection
init_langfuse()


# Langfuse middleware - sets user email for all traces (only if Langfuse is available)
async def langfuse_user_middleware(context, call_next):
    """Set Langfuse user context from authenticated Google OAuth user."""
    if is_langfuse_available() and hasattr(context, 'user') and context.user:
        user_email = getattr(context.user, 'email', None) or str(context.user)
        langfuse = get_client()
        langfuse.update_current_trace(user_id=user_email)
        logger.debug(f"Langfuse trace user: {user_email}")
    
    return await call_next(context)

mcp.add_middleware(langfuse_user_middleware)
logger.info("Langfuse user tracking middleware enabled")


def register_tools():
    """Register all tools and prompts with the MCP server."""
    from lineage_server.tools.ping import ping
    from lineage_server.tools.resolve_input import resolve_input
    from lineage_server.tools.column_lineage import generate_column_lineage
    from lineage_server.tools.model_lineage import generate_model_lineage
    from lineage_server.prompts import lineage_workflow_instructions

    # Register tools (each tool has @observe decorator for Langfuse tracing)
    logger.debug("Registering tool: ping")
    mcp.tool(description="Test if the MCP server is responding")(ping)
    
    logger.debug("Registering tool: resolve_input")
    mcp.tool(description="CALL THIS FIRST for any lineage request. Validates data_product, model_name, and optional column_name. Returns available options if validation fails.")(resolve_input)
    
    logger.debug("Registering tool: generate_column_lineage")
    mcp.tool(description="Generate column lineage by tracing a column through upstream dbt models and sources. Call resolve_input first to validate inputs unless user explicitly requests this tool.")(generate_column_lineage)
    
    logger.debug("Registering tool: generate_model_lineage")
    mcp.tool(description="Generate model lineage by tracing upstream dependencies of a dbt model. Call resolve_input first to validate inputs unless user explicitly requests this tool.")(generate_model_lineage)
    
    # Register prompts
    logger.debug("Registering prompt: lineage_workflow")
    mcp.prompt(
        name="lineage_workflow",
        description="Instructions for AI agents on how to use lineage tools"
    )(lineage_workflow_instructions)
    
    logger.info("All tools and prompts registered successfully")

    