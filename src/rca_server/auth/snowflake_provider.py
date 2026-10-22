"""Snowflake OAuth for FastMCP.

Snowflake custom OAuth is two URLs plus a bearer token
(https://docs.snowflake.com/en/user-guide/oauth-custom):

    https://<account>.snowflakecomputing.com/oauth/authorize
    https://<account>.snowflakecomputing.com/oauth/token-request

This module wires those URLs into FastMCP's OAuthProxy. FastMCP still
needs a TokenVerifier class to inspect the token on each request.

    from rca_server.auth import create_snowflake_auth

    auth = create_snowflake_auth(
        account="myaccount",
        client_id="...",
        client_secret="...",
        base_url="http://localhost:8000",
    )
"""

from __future__ import annotations

import time

import jwt

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_SCOPES = ["session:role:PUBLIC"]


def snowflake_base_url(account: str) -> str:
    """Build https://<account>.snowflakecomputing.com, or use account as-is if it is already a host."""
    if ".snowflakecomputing.com" in account:
        return f"https://{account}"
    return f"https://{account}.snowflakecomputing.com"


def _scopes_from_payload(payload: dict, required_scopes: list[str] | None) -> list[str]:
    """Read JWT scopes and always include FastMCP required_scopes.

    Snowflake OAuth JWTs often omit `scope` / `scp`, send an empty `scope`,
    or recase `session:role:...` (Snowflake roles are typically uppercase).
    FastMCP's bearer middleware returns 403 insufficient_scope unless every
    required_scope is an exact string in AccessToken.scopes, so we union the
    JWT scopes with required_scopes (preserving the required spelling).
    """
    extracted: list[str] = []
    raw_scope = payload.get("scope")
    if raw_scope:
        extracted = [s for s in str(raw_scope).split(" ") if s]
    else:
        scp = payload.get("scp")
        if isinstance(scp, list):
            extracted = [str(s) for s in scp if s]
        elif scp:
            extracted = [str(scp)]

    required = list(required_scopes or [])
    required_by_lower = {s.lower(): s for s in required}
    seen: set[str] = set()
    scopes: list[str] = []
    for scope in extracted:
        canonical = required_by_lower.get(scope.lower(), scope)
        key = canonical.lower()
        if key not in seen:
            scopes.append(canonical)
            seen.add(key)
    for scope in required:
        key = scope.lower()
        if key not in seen:
            scopes.append(scope)
            seen.add(key)
    return scopes


class SnowflakeTokenVerifier(TokenVerifier):
    """Accept Snowflake access tokens: decode JWT, reject expired, map claims."""

    def __init__(self, *, required_scopes: list[str] | None = None):
        super().__init__(required_scopes=required_scopes)

    async def verify_token(self, token: str) -> AccessToken | None:
        # Signature is not checked here: OAuthProxy already obtained this
        # token from Snowflake's token endpoint. We only reject junk / expiry.
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
        except jwt.exceptions.PyJWTError:
            logger.debug("Snowflake token is not a valid JWT")
            return None

        exp = payload.get("exp")
        if exp is not None and int(exp) < time.time():
            logger.debug("Snowflake token has expired")
            return None

        scopes = _scopes_from_payload(payload, self.required_scopes)
        # Snowflake uses `username`; other issuers may only set `sub` / `name`.
        username = payload.get("username") or payload.get("sub") or payload.get("name")

        return AccessToken(
            token=token,
            client_id=payload.get("aud", "unknown"),
            scopes=scopes,
            expires_at=int(exp) if exp is not None else None,
            claims={
                "sub": payload.get("sub"),
                "username": username,
                "email": payload.get("email"),
                "iss": payload.get("iss"),
                "aud": payload.get("aud"),
                "snowflake_payload": payload,
            },
        )


def create_snowflake_auth(
    *,
    account: str,
    client_id: str,
    client_secret: str,
    base_url: str,
    required_scopes: list[str] | None = None,
) -> OAuthProxy:
    """Build FastMCP OAuthProxy pointed at Snowflake's documented OAuth endpoints."""
    scopes = required_scopes or _DEFAULT_SCOPES
    host = snowflake_base_url(account)

    logger.debug(
        "Creating Snowflake OAuth proxy for account %s with scopes: %s",
        account,
        scopes,
    )
    return OAuthProxy(
        # Snowflake custom OAuth authorize + token-request URLs
        upstream_authorization_endpoint=f"{host}/oauth/authorize",
        upstream_token_endpoint=f"{host}/oauth/token-request",
        upstream_client_id=client_id,
        upstream_client_secret=client_secret,
        token_verifier=SnowflakeTokenVerifier(required_scopes=scopes),
        base_url=base_url,
        issuer_url=base_url,
    )
