"""Tests for the ping tool."""

import pytest

from lineage_server.tools.ping import ping


class TestPing:
    """Test cases for the ping tool."""

    @pytest.mark.asyncio
    async def test_ping_returns_success(self):
        """Test that ping returns a successful response."""
        result = await ping()

        assert result["success"] is True
        assert result["message"] == "pong - lineage server is running"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_ping_includes_tracing_status(self):
        """Test that ping includes Langfuse tracing status."""
        result = await ping()

        assert "tracing" in result
        assert "enabled" in result["tracing"]
        assert "error" in result["tracing"]
        # enabled should be a boolean
        assert isinstance(result["tracing"]["enabled"], bool)

    @pytest.mark.asyncio
    async def test_ping_timestamp_is_iso_format(self):
        """Test that timestamp is in ISO format."""
        result = await ping()

        timestamp = result["timestamp"]
        # Should be parseable as ISO format (contains T and timezone info)
        assert "T" in timestamp
        assert "+" in timestamp or "Z" in timestamp

    @pytest.mark.asyncio
    async def test_ping_tracing_disabled_without_credentials(
        self, mock_langfuse_disabled
    ):
        """Test that tracing shows disabled when Langfuse is not configured."""
        result = await ping()

        assert result["tracing"]["enabled"] is False
        assert result["tracing"]["error"] == "Langfuse credentials not configured"

    @pytest.mark.asyncio
    async def test_ping_tracing_enabled_with_credentials(self, mock_langfuse_enabled):
        """Test that tracing shows enabled when Langfuse is configured."""
        result = await ping()

        assert result["tracing"]["enabled"] is True
        assert result["tracing"]["error"] is None
