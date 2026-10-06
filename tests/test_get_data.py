"""Tests for the get_data tool."""

import os
from unittest.mock import patch, MagicMock

import pytest

from rca_server.tools.get_data import get_data, _enforce_limit


SNOWFLAKE_ENV = {
    "SNOWFLAKE_ACCOUNT": "test-account",
    "SNOWFLAKE_USER": "test-user",
    "SNOWFLAKE_PASSWORD": "test-pass",
    "SNOWFLAKE_ROLE": "TEST_ROLE",
    "SNOWFLAKE_DATABASE": "TEST_DB",
    "SNOWFLAKE_WAREHOUSE": "TEST_WH",
}


class TestEnforceLimit:
    """Test cases for the _enforce_limit helper function."""

    def test_adds_limit_when_missing(self):
        """Test that LIMIT 10 is added to queries without a LIMIT."""
        result = _enforce_limit("SELECT * FROM users")
        assert "LIMIT 10" in result.upper()

    def test_caps_high_limit(self):
        """Test that LIMIT > 10 is capped to 10."""
        result = _enforce_limit("SELECT * FROM users LIMIT 100")
        assert "LIMIT 10" in result.upper()
        assert "100" not in result


class TestGetData:
    """Test cases for the get_data tool."""

    @pytest.mark.asyncio
    async def test_successful_query(self):
        """Test successful query returns rows as list of dicts."""
        mock_rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.dict(os.environ, SNOWFLAKE_ENV):
            with patch("snowflake.connector.connect", return_value=mock_conn):
                result = await get_data("SELECT id, name FROM users")

                assert result["success"] is True
                assert result["row_count"] == 2
                assert len(result["data"]) == 2
                assert result["error_details"] is None
