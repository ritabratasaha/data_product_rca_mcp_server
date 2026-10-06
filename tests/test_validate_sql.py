"""Tests for the validate_sql tool."""

import os
from unittest.mock import patch, MagicMock

import pytest

from rca_server.tools.validate_sql import validate_sql, _check_query_policy


SNOWFLAKE_ENV = {
    "SNOWFLAKE_ACCOUNT": "test-account",
    "SNOWFLAKE_USER": "test-user",
    "SNOWFLAKE_PASSWORD": "test-pass",
    "SNOWFLAKE_ROLE": "TEST_ROLE",
    "SNOWFLAKE_DATABASE": "TEST_DB",
    "SNOWFLAKE_WAREHOUSE": "TEST_WH",
}


class TestCheckQueryPolicy:
    """Test cases for the _check_query_policy helper function."""

    def test_select_with_columns_allowed(self):
        """Test that SELECT with explicit columns is allowed."""
        is_valid, error = _check_query_policy("SELECT id, name FROM users")
        assert is_valid is True
        assert error is None

    def test_select_star_rejected(self):
        """Test that SELECT * is rejected."""
        is_valid, error = _check_query_policy("SELECT * FROM users")
        assert is_valid is False
        assert "explicit column names" in error


class TestValidateSql:
    """Test cases for the validate_sql tool."""

    @pytest.mark.asyncio
    async def test_missing_database_url(self):
        """Test error when Snowflake credentials are not set."""
        with patch.dict(os.environ, {}, clear=True):
            for key in SNOWFLAKE_ENV:
                os.environ.pop(key, None)

            result = await validate_sql("SELECT id FROM users")

            assert result["success"] is False
            assert "not configured" in result["error_details"]

    @pytest.mark.asyncio
    async def test_valid_sql_returns_success(self):
        """Test that valid SQL returns success response."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.dict(os.environ, SNOWFLAKE_ENV):
            with patch("snowflake.connector.connect", return_value=mock_conn):
                result = await validate_sql("SELECT id, name FROM users")

                assert result["success"] is True
                assert "valid" in result["message"].lower()
                assert result["error_details"] is None

    @pytest.mark.asyncio
    async def test_syntax_error_returns_failure(self):
        """Test that SQL syntax error returns proper error response."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("SQL compilation error: syntax error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.dict(os.environ, SNOWFLAKE_ENV):
            with patch("snowflake.connector.connect", return_value=mock_conn):
                result = await validate_sql("SELECT id FROM users WHERE")

                assert result["success"] is False
                assert result["error_details"] is not None
