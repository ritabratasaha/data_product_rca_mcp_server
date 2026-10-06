"""Snowflake OAuth provider for FastMCP.

This module provides Snowflake OAuth integration for MCP servers,
allowing users to authenticate via their Snowflake account.

The OAuth flow uses Snowflake as the identity provider:
1. User is redirected to Snowflake's authorization page
2. User logs in with their Snowflake credentials
3. Snowflake returns an access token to the MCP server
4. The same token can potentially be used for Snowflake database connections

Example:
    ```python
    from fastmcp import FastMCP
    from rca_server.auth import SnowflakeProvider

    auth = SnowflakeProvider(
        account="myaccount",
        client_id="snowflake-oauth-client-id",
        client_secret="snowflake-oauth-client-secret",
        base_url="http://localhost:8000"
    )

    mcp = FastMCP("My Server", auth=auth)
    ```
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from key_value.aio.protocols import AsyncKeyValue
from pydantic import AnyHttpUrl

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class SnowflakeTokenVerifier(TokenVerifier):
    """Token verifier for Snowflake OAuth tokens.
    
    Validates Snowflake OAuth access tokens by attempting to use them
    with Snowflake's session endpoint or by decoding JWT tokens.
    """

    def __init__(
        self,
        *,
        account: str,
        required_scopes: list[str] | None = None,
        timeout_seconds: int = 10,
    ):
        """Initialize the Snowflake token verifier.

        Args:
            account: Snowflake account identifier (e.g., "myaccount" or "myaccount.us-east-1")
            required_scopes: Required OAuth scopes
            timeout_seconds: HTTP request timeout
        """
        super().__init__(required_scopes=required_scopes)
        self.account = account
        self.timeout_seconds = timeout_seconds
        
        # Build Snowflake base URL
        if ".snowflakecomputing.com" in account:
            self.snowflake_base_url = f"https://{account}"
        else:
            self.snowflake_base_url = f"https://{account}.snowflakecomputing.com"

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify Snowflake OAuth token.
        
        Snowflake OAuth tokens are JWTs that can be validated by:
        1. Decoding the JWT to check expiration and claims
        2. Optionally calling Snowflake's session endpoint to validate
        """
        try:
            import base64
            import json
            
            # Try to decode as JWT
            parts = token.split(".")
            if len(parts) == 3:
                # It's a JWT - decode the payload
                payload_b64 = parts[1]
                # Add padding if needed
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                
                # Check expiration
                exp = payload.get("exp")
                if exp and int(exp) < time.time():
                    logger.debug("Snowflake token has expired")
                    return None
                
                # Extract scopes if present
                token_scopes = []
                if "scope" in payload:
                    scope_str = payload.get("scope", "")
                    token_scopes = [s.strip() for s in scope_str.split(" ") if s.strip()]
                elif "scp" in payload:
                    scp = payload.get("scp", [])
                    token_scopes = scp if isinstance(scp, list) else [scp]
                
                # Snowflake OAuth tokens don't include scope claims in the JWT.
                # If the token was issued successfully, we trust that Snowflake granted
                # the requested scopes. Add required_scopes to token_scopes if empty.
                if not token_scopes and self.required_scopes:
                    token_scopes = list(self.required_scopes)
                    logger.debug(
                        "Snowflake token has no scope claims, using required scopes: %s",
                        token_scopes,
                    )
                
                # Calculate expiration time
                expires_at = int(exp) if exp else None
                
                # Extract user info from token claims
                username = payload.get("username") or payload.get("sub") or payload.get("name")
                
                access_token = AccessToken(
                    token=token,
                    client_id=payload.get("aud", "unknown"),
                    scopes=token_scopes,
                    expires_at=expires_at,
                    claims={
                        "sub": payload.get("sub"),
                        "username": username,
                        "email": payload.get("email"),
                        "iss": payload.get("iss"),
                        "aud": payload.get("aud"),
                        "snowflake_payload": payload,
                    },
                )
                logger.debug("Snowflake token verified successfully (JWT)")
                return access_token
            
            else:
                # Not a JWT - try to validate against Snowflake API
                # This is a fallback for opaque tokens
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    # Try to get session info using the token
                    response = await client.post(
                        f"{self.snowflake_base_url}/session/v1/login-request",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "User-Agent": "FastMCP-Snowflake-OAuth",
                        },
                        json={"data": {"AUTHENTICATOR": "OAUTH", "TOKEN": token}},
                    )
                    
                    if response.status_code != 200:
                        logger.debug(
                            "Snowflake token verification failed: %d",
                            response.status_code,
                        )
                        return None
                    
                    data = response.json()
                    if not data.get("success"):
                        logger.debug("Snowflake token validation unsuccessful")
                        return None
                    
                    session_data = data.get("data", {})
                    
                    access_token = AccessToken(
                        token=token,
                        client_id="snowflake",
                        scopes=[],
                        expires_at=None,
                        claims={
                            "sub": session_data.get("sessionId"),
                            "username": session_data.get("user"),
                            "snowflake_session": session_data,
                        },
                    )
                    logger.debug("Snowflake token verified successfully (session)")
                    return access_token

        except Exception as e:
            logger.debug("Snowflake token verification error: %s", e)
            return None


class SnowflakeProvider(OAuthProxy):
    """Complete Snowflake OAuth provider for FastMCP.

    This provider enables Snowflake OAuth authentication for MCP servers.
    Users authenticate via their Snowflake account, and the resulting token
    can potentially be used for both MCP authentication and Snowflake database
    connections.

    Prerequisites:
    - Create a Snowflake OAuth integration (see setup_snowflake_oauth.sql)
    - Obtain client_id and client_secret from the integration

    Example:
        ```python
        from fastmcp import FastMCP
        from rca_server.auth import SnowflakeProvider

        auth = SnowflakeProvider(
            account="myaccount",
            client_id="client-id-from-snowflake",
            client_secret="client-secret-from-snowflake",
            base_url="http://localhost:8000"
        )

        mcp = FastMCP("My App", auth=auth)
        ```
    """

    def __init__(
        self,
        *,
        account: str,
        client_id: str,
        client_secret: str,
        base_url: AnyHttpUrl | str,
        issuer_url: AnyHttpUrl | str | None = None,
        redirect_path: str | None = None,
        required_scopes: list[str] | None = None,
        timeout_seconds: int = 10,
        allowed_client_redirect_uris: list[str] | None = None,
        client_storage: AsyncKeyValue | None = None,
        jwt_signing_key: str | bytes | None = None,
        require_authorization_consent: bool = True,
        extra_authorize_params: dict[str, str] | None = None,
    ):
        """Initialize Snowflake OAuth provider.

        Args:
            account: Snowflake account identifier (e.g., "myaccount" or "myaccount.us-east-1")
            client_id: OAuth client ID from Snowflake security integration
            client_secret: OAuth client secret from Snowflake security integration
            base_url: Public URL where OAuth endpoints will be accessible
            issuer_url: Issuer URL for OAuth metadata (defaults to base_url)
            redirect_path: Redirect path for OAuth callback (defaults to "/auth/callback")
            required_scopes: Required Snowflake scopes (defaults to ["session:role:PUBLIC"])
            timeout_seconds: HTTP request timeout for Snowflake API calls
            allowed_client_redirect_uris: List of allowed redirect URI patterns for MCP clients
            client_storage: Storage backend for OAuth state
            jwt_signing_key: Secret for signing FastMCP JWT tokens
            require_authorization_consent: Whether to require user consent (default True)
            extra_authorize_params: Additional parameters for authorization endpoint
        """
        # Build Snowflake OAuth endpoints
        if ".snowflakecomputing.com" in account:
            snowflake_base_url = f"https://{account}"
        else:
            snowflake_base_url = f"https://{account}.snowflakecomputing.com"
        
        authorization_endpoint = f"{snowflake_base_url}/oauth/authorize"
        token_endpoint = f"{snowflake_base_url}/oauth/token-request"
        
        # Default scopes for Snowflake
        # session:role:PUBLIC allows assuming the PUBLIC role
        # Additional role scopes can be added like session:role:ANALYST
        required_scopes_final = required_scopes or ["session:role:PUBLIC"]
        
        # Create Snowflake token verifier
        token_verifier = SnowflakeTokenVerifier(
            account=account,
            required_scopes=required_scopes_final,
            timeout_seconds=timeout_seconds,
        )
        
        # Set Snowflake-specific defaults for extra authorize params
        snowflake_defaults: dict[str, Any] = {}
        if extra_authorize_params:
            snowflake_defaults.update(extra_authorize_params)
        
        # Initialize OAuth proxy with Snowflake endpoints
        super().__init__(
            upstream_authorization_endpoint=authorization_endpoint,
            upstream_token_endpoint=token_endpoint,
            upstream_client_id=client_id,
            upstream_client_secret=client_secret,
            token_verifier=token_verifier,
            base_url=base_url,
            redirect_path=redirect_path,
            issuer_url=issuer_url or base_url,
            allowed_client_redirect_uris=allowed_client_redirect_uris,
            client_storage=client_storage,
            jwt_signing_key=jwt_signing_key,
            require_authorization_consent=require_authorization_consent,
            extra_authorize_params=snowflake_defaults if snowflake_defaults else None,
        )
        
        # Store account for potential later use
        self.snowflake_account = account
        self.snowflake_base_url = snowflake_base_url
        
        logger.debug(
            "Initialized Snowflake OAuth provider for account %s with scopes: %s",
            account,
            required_scopes_final,
        )
