"""Shared Snowflake connection utility with OAuth support."""

import os
from contextvars import ContextVar

import snowflake.connector

from rca_server.logger import get_logger

logger = get_logger("snowflake_connection")

# Testing mode - uses dedicated testing credentials instead of OAuth
TESTING_MODE = os.getenv("TESTING", "").lower() in ("true", "1", "yes")

# OAuth token context variable - set by middleware during authenticated requests
# This allows the same OAuth token used for MCP authentication to be reused
# for Snowflake database connections
oauth_token: ContextVar[str | None] = ContextVar('oauth_token', default=None)


def get_snowflake_connection(**kwargs):
    """
    Get Snowflake connection using OAuth or username/password authentication.
    
    Authentication priority:
    1. OAuth token (if available via context variable, set by middleware)
    2. Testing credentials (if TESTING=true, uses TESTING_SNOWFLAKE_USER/PASSWORD)
    3. Username/password from environment variables (fallback)
    
    Environment variables used:
    - SNOWFLAKE_ACCOUNT (required)
    - SNOWFLAKE_DATABASE
    - SNOWFLAKE_WAREHOUSE
    - SNOWFLAKE_ROLE (used with OAuth)
    - SNOWFLAKE_USER (for password auth fallback)
    - SNOWFLAKE_PASSWORD (for password auth fallback)
    - TESTING_SNOWFLAKE_USER (for testing mode)
    - TESTING_SNOWFLAKE_PASSWORD (for testing mode)
    
    Args:
        **kwargs: Additional arguments to pass to snowflake.connector.connect()
        
    Returns:
        snowflake.connector.Connection: Active Snowflake connection
        
    Raises:
        Exception: If connection fails
    """
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    database = os.getenv("SNOWFLAKE_DATABASE")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    role = os.getenv("SNOWFLAKE_ROLE")
    
    # Check if OAuth token is available (set by middleware)
    token = oauth_token.get()
    
    if token:
        # Use OAuth authentication with the token from MCP auth
        # Note: Don't specify role here - the OAuth token includes the role in its scopes
        # (e.g., session:role:PUBLIC). Snowflake will use the role from the token.
        logger.debug("Connecting to Snowflake with OAuth token")
        return snowflake.connector.connect(
            account=account,
            authenticator='oauth',
            token=token,
            database=database,
            warehouse=warehouse,
            **kwargs
        )
    elif TESTING_MODE:
        # Use testing credentials (minimal PUBLIC role user for CI/evals)
        user = os.getenv("TESTING_SNOWFLAKE_USER")
        password = os.getenv("TESTING_SNOWFLAKE_PASSWORD")
        
        logger.debug("Connecting to Snowflake with TESTING credentials (PUBLIC role)")
        return snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            role="PUBLIC",
            database=database,
            warehouse=warehouse,
            **kwargs
        )
    else:
        # Fallback to username/password authentication
        user = os.getenv("SNOWFLAKE_USER")
        password = os.getenv("SNOWFLAKE_PASSWORD")
        
        logger.debug("Connecting to Snowflake with username/password authentication")
        return snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            role=role,
            database=database,
            warehouse=warehouse,
            **kwargs
        )
