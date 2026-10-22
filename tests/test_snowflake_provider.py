"""Unit tests for Snowflake JWT token verification and OAuth factory."""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest

from rca_server.auth.snowflake_provider import (
    SnowflakeTokenVerifier,
    create_snowflake_auth,
    snowflake_base_url,
)


def _jwt(payload: dict) -> str:
    return jwt.encode(payload, "test-secret-key-32-bytes-minimum!", algorithm="HS256")


class TestSnowflakeBaseUrl:
    def test_account_locator(self):
        assert snowflake_base_url("xy12345") == "https://xy12345.snowflakecomputing.com"

    def test_full_host(self):
        assert (
            snowflake_base_url("xy12345.us-east-1.snowflakecomputing.com")
            == "https://xy12345.us-east-1.snowflakecomputing.com"
        )


class TestSnowflakeTokenVerifier:
    def setup_method(self):
        self.verifier = SnowflakeTokenVerifier(
            required_scopes=["session:role:PUBLIC"],
        )

    @pytest.mark.asyncio
    async def test_expired_jwt_returns_none(self):
        token = _jwt({"exp": int(time.time()) - 60, "username": "alice"})
        assert await self.verifier.verify_token(token) is None

    @pytest.mark.asyncio
    async def test_valid_jwt_without_scope_uses_required_scopes(self):
        token = _jwt({
            "exp": int(time.time()) + 3600,
            "username": "alice",
            "sub": "alice",
        })
        result = await self.verifier.verify_token(token)
        assert result is not None
        assert result.scopes == ["session:role:PUBLIC"]
        assert result.claims["username"] == "alice"

    @pytest.mark.asyncio
    async def test_empty_scope_claim_uses_required_scopes(self):
        token = _jwt({
            "exp": int(time.time()) + 3600,
            "username": "alice",
            "scope": "",
        })
        result = await self.verifier.verify_token(token)
        assert result is not None
        assert result.scopes == ["session:role:PUBLIC"]

    @pytest.mark.asyncio
    async def test_uppercase_scp_normalizes_to_required_scope(self):
        verifier = SnowflakeTokenVerifier(
            required_scopes=["session:role:flight_analyst_role"],
        )
        token = _jwt({
            "exp": int(time.time()) + 3600,
            "username": "alice",
            "scp": ["refresh_token", "session:role:FLIGHT_ANALYST_ROLE"],
        })
        result = await verifier.verify_token(token)
        assert result is not None
        assert "session:role:flight_analyst_role" in result.scopes
        assert "refresh_token" in result.scopes

    @pytest.mark.asyncio
    async def test_non_jwt_returns_none(self):
        assert await self.verifier.verify_token("not-a-jwt") is None


class TestCreateSnowflakeAuth:
    def test_passes_snowflake_oauth_urls_to_proxy(self):
        with patch(
            "rca_server.auth.snowflake_provider.OAuthProxy",
            return_value=MagicMock(),
        ) as mock_proxy:
            create_snowflake_auth(
                account="xy12345",
                client_id="client",
                client_secret="secret",
                base_url="http://localhost:8000",
            )
        kwargs = mock_proxy.call_args.kwargs
        assert (
            kwargs["upstream_token_endpoint"]
            == "https://xy12345.snowflakecomputing.com/oauth/token-request"
        )
        assert (
            kwargs["upstream_authorization_endpoint"]
            == "https://xy12345.snowflakecomputing.com/oauth/authorize"
        )
        assert isinstance(kwargs["token_verifier"], SnowflakeTokenVerifier)
