"""Tests for the ping tool."""

import pytest

from rca_server.tools.ping import ping


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
