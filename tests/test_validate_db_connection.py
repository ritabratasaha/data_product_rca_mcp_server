"""Tests for the validate_db_connection tool."""

import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest

from rca_server.tools.validate_db_connection import validate_db_connection


SNOWFLAKE_ENV = {
    "SNOWFLAKE_ACCOUNT": "test-account",
    "SNOWFLAKE_USER": "test-user",
    "SNOWFLAKE_PASSWORD": "test-pass",
    "SNOWFLAKE_ROLE": "TEST_ROLE",
    "SNOWFLAKE_DATABASE": "TEST_DB",
    "SNOWFLAKE_WAREHOUSE": "TEST_WH",
}


class TestValidateDbConnection:
    """Test cases for the validate_db_connection tool."""

    @pytest.mark.asyncio
    async def test_missing_snowflake_config(self):
        """Test error when Snowflake credentials are not set."""
        with patch.dict(os.environ, {}, clear=True):
            for key in SNOWFLAKE_ENV:
                os.environ.pop(key, None)

            result = await validate_db_connection()

            assert result["success"] is False
            assert "Snowflake credentials not configured" in result["error_details"]
            assert result["server_time"] is None

    @pytest.mark.asyncio
    async def test_successful_connection(self):
        """Test successful database connection returns server time."""
        mock_time = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (mock_time,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.dict(os.environ, SNOWFLAKE_ENV):
            with patch("snowflake.connector.connect", return_value=mock_conn):
                result = await validate_db_connection()

                assert result["success"] is True
                assert result["server_time"] is not None
                assert "up and running" in result["message"]
                assert result["error_details"] is None
