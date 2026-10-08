"""Tool registry using FastMCP with Snowflake OAuth authentication.

Snowflake OAuth configuration:
- SNOWFLAKE_ACCOUNT
- SNOWFLAKE_OAUTH_CLIENT_ID
- SNOWFLAKE_OAUTH_CLIENT_SECRET
- SNOWFLAKE_OAUTH_ROLES (optional, defaults to "PUBLIC")

Testing mode:
- Set TESTING=true to disable authentication (for CI/testing environments)
"""

import os

from fastmcp import FastMCP
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

# Optional Prometheus metrics (observatory_sdk may not be installed)
try:
    from observatory_sdk import instrument as prometheus_instrument
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    prometheus_instrument = None

# Optional Langfuse (may not be installed)
try:
    from langfuse import get_client
    LANGFUSE_IMPORT_AVAILABLE = True
except ImportError:
    LANGFUSE_IMPORT_AVAILABLE = False
    get_client = None

from rca_server.logger import get_logger
from rca_server.manifest_utils import load_data_product_config

# Optional langfuse connection manager
try:
    import rca_server.langfuse_connection_manager as langfuse_manager
except ImportError:
    langfuse_manager = None

logger = get_logger("registry")

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000")

# Testing mode - disables authentication for CI/testing environments
TESTING_MODE = os.getenv("TESTING", "").lower() in ("true", "1", "yes")

# Initialize auth (skip if TESTING mode, otherwise use Snowflake OAuth)
auth = None

if TESTING_MODE:
    logger.info("TESTING mode enabled - authentication disabled")
else:
    # Snowflake OAuth configuration
    from rca_server.auth import SnowflakeProvider
    
    SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
    SNOWFLAKE_OAUTH_CLIENT_ID = os.getenv("SNOWFLAKE_OAUTH_CLIENT_ID")
    SNOWFLAKE_OAUTH_CLIENT_SECRET = os.getenv("SNOWFLAKE_OAUTH_CLIENT_SECRET")
    SNOWFLAKE_OAUTH_ROLES = os.getenv("SNOWFLAKE_OAUTH_ROLES", "PUBLIC")
    
    if SNOWFLAKE_ACCOUNT and SNOWFLAKE_OAUTH_CLIENT_ID and SNOWFLAKE_OAUTH_CLIENT_SECRET:
        # Build scopes from roles
        role_scopes = [
            f"session:role:{role.strip()}"
            for role in SNOWFLAKE_OAUTH_ROLES.split(",")
            if role.strip()
        ]
        
        auth = SnowflakeProvider(
            account=SNOWFLAKE_ACCOUNT,
            client_id=SNOWFLAKE_OAUTH_CLIENT_ID,
            client_secret=SNOWFLAKE_OAUTH_CLIENT_SECRET,
            base_url=SERVER_BASE_URL,
            required_scopes=role_scopes,
        )
        logger.info(f"Snowflake OAuth configured for account: {SNOWFLAKE_ACCOUNT}")
        logger.info(f"Snowflake OAuth scopes: {role_scopes}")
    else:
        missing = []
        if not SNOWFLAKE_ACCOUNT:
            missing.append("SNOWFLAKE_ACCOUNT")
        if not SNOWFLAKE_OAUTH_CLIENT_ID:
            missing.append("SNOWFLAKE_OAUTH_CLIENT_ID")
        if not SNOWFLAKE_OAUTH_CLIENT_SECRET:
            missing.append("SNOWFLAKE_OAUTH_CLIENT_SECRET")
        logger.warning(f"Snowflake OAuth credentials missing: {', '.join(missing)}")
        logger.warning("Authentication disabled")

mcp = FastMCP("rca-server", auth=auth)

# Prometheus metrics instrumentation (skip if TESTING mode or observatory_sdk not installed)
if not TESTING_MODE and PROMETHEUS_AVAILABLE:
    prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))
    try:
        prometheus_instrument(mcp, service_name="rca-server", prometheus_port=prometheus_port)
        logger.info(f"Prometheus metrics enabled on port {prometheus_port}")
    except OSError as e:
        logger.warning(f"Could not start Prometheus server: {e}")
elif not PROMETHEUS_AVAILABLE:
    logger.info("Prometheus metrics disabled (observatory_sdk not installed)")
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

# Import OAuth token context for Snowflake connection reuse
from rca_server.snowflake_connection import oauth_token

# Import SDK's auth context to get access token
from mcp.server.auth.middleware.auth_context import get_access_token


# OAuth token middleware - captures token for Snowflake database connections
async def oauth_token_middleware(context, call_next):
    """Capture OAuth token from context for Snowflake database connections.
    
    This middleware extracts the OAuth access token from the authenticated
    request context and stores it in a context variable. The token is then
    used by snowflake_connection.py to authenticate database connections
    using the same OAuth credentials used for MCP authentication.
    """
    # Use MCP SDK's auth context to get the access token
    access_token = get_access_token()
    if access_token:
        token_value = getattr(access_token, 'token', None)
        if token_value:
            oauth_token.set(token_value)
            logger.debug("OAuth token captured for Snowflake connection")
    
    return await call_next(context)

mcp.add_middleware(oauth_token_middleware)
logger.info("OAuth token middleware enabled for Snowflake connection reuse")

# Initialize Langfuse connection (if available)
if langfuse_manager:
    langfuse_manager.init_langfuse()


# Langfuse middleware - sets user from OAuth for all traces
async def langfuse_user_middleware(context, call_next):
    """Set Langfuse user context from authenticated Snowflake OAuth user."""
    if LANGFUSE_IMPORT_AVAILABLE and langfuse_manager and langfuse_manager.langfuse_available and hasattr(context, 'user') and context.user:
        # Get user identifier from Snowflake OAuth
        user_id = (
            getattr(context.user, 'email', None) or 
            getattr(context.user, 'username', None) or 
            str(context.user)
        )
        langfuse = get_client()
        langfuse.update_current_trace(user_id=user_id)
        logger.debug(f"Langfuse trace user: {user_id}")
    
    return await call_next(context)

mcp.add_middleware(langfuse_user_middleware)
if LANGFUSE_IMPORT_AVAILABLE:
    logger.info("Langfuse user tracking middleware enabled")
else:
    logger.info("Langfuse disabled (not installed)")


def register_tools():
    """Register all tools and prompts with the MCP server."""
    from rca_server.tools.ping import ping
    from rca_server.tools.resolve_input import resolve_input
    from rca_server.tools.column_lineage import generate_column_lineage
    from rca_server.tools.model_lineage import generate_model_lineage
    from rca_server.tools.validate_sql import validate_sql
    from rca_server.tools.validate_db_connection import validate_db_connection
    from rca_server.tools.get_data import get_data
    from rca_server.tools.get_airflow_dag_runs import get_airflow_dag_runs
    from rca_server.prompts import lineage_workflow_instructions

    # Build mapping string from data_products.json for tool descriptions
    config = load_data_product_config()
    products_str = ", ".join(
        f"{name} (DB: {info.get('database_name', '?')}, DAG: {info.get('airflow_dag_name', '?')})"
        for name, info in config.items()
    )
    mapping_suffix = f" Available data products: {products_str}." if products_str else ""

    # Register tools (each tool has @observe decorator for Langfuse tracing)
    logger.debug("Registering tool: ping")
    mcp.tool(description="Test if the MCP server is responding")(ping)
    
    logger.debug("Registering tool: resolve_input")
    mcp.tool(description="CALL THIS FIRST for any lineage request. Validates data_product, model_name, and optional column_name. Returns available options if validation fails. NEVER assume data_product from context — always ask the user or call this tool to list available data products." + mapping_suffix)(resolve_input)
    
    logger.debug("Registering tool: generate_column_lineage")
    mcp.tool(description="Generate column lineage by tracing a column through upstream dbt models and sources. Automatically validates inputs before tracing. NEVER assume data_product — ask the user if not explicitly provided.")(generate_column_lineage)
    
    logger.debug("Registering tool: generate_model_lineage")
    mcp.tool(description="Generate model lineage by tracing upstream dependencies of a dbt model. Automatically validates inputs before tracing. NEVER assume data_product — ask the user if not explicitly provided.")(generate_model_lineage)
    
    logger.debug("Registering tool: validate_sql")
    mcp.tool(description="Validate SQL syntax and schema references against Snowflake without executing. Returns success/failure with error details.")(validate_sql)
    
    logger.debug("Registering tool: validate_db_connection")
    mcp.tool(description="Test if the Snowflake database is up and running. Call before validate_sql.")(validate_db_connection)
    
    logger.debug("Registering tool: get_data")
    mcp.tool(description="Execute a read-only SELECT query against Snowflake and return up to 10 rows. Call validate_db_connection and validate_sql first.")(get_data)
    
    logger.debug("Registering tool: get_airflow_dag_runs")
    mcp.tool(description="Get Airflow DAG run details for a specific date: run count, status, duration, 7-day avg, and task logs.")(get_airflow_dag_runs)
    
    # Register prompts
    logger.debug("Registering prompt: lineage_workflow")
    mcp.prompt(
        name="lineage_workflow",
        description="Instructions for AI agents on how to use lineage tools"
    )(lineage_workflow_instructions)
    
    logger.info("All tools and prompts registered successfully")
