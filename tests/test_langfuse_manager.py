"""Tests for the langfuse_connection_manager module."""

import os
from unittest.mock import patch, MagicMock

import pytest

from lineage_server.langfuse_connection_manager import (
    init_langfuse,
    is_langfuse_available,
    get_langfuse_status,
)


class TestInitLangfuse:
    """Test cases for the init_langfuse function."""

    def test_init_with_placeholder_credentials(self):
        """Test that placeholder credentials result in disabled Langfuse."""
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-lf-placeholder",
                "LANGFUSE_SECRET_KEY": "sk-lf-placeholder",
            },
        ):
            # Reset module state
            import lineage_server.langfuse_connection_manager as lcm

            lcm._langfuse_available = False
            lcm._langfuse_error = None

            result = init_langfuse()

            assert result is False
            assert is_langfuse_available() is False
            status = get_langfuse_status()
            assert status["langfuse_available"] is False
            assert "not configured" in status["langfuse_error"]

    def test_init_with_missing_credentials(self):
        """Test that missing credentials result in disabled Langfuse."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure LANGFUSE_PUBLIC_KEY is not set
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)

            import lineage_server.langfuse_connection_manager as lcm

            lcm._langfuse_available = False
            lcm._langfuse_error = None

            result = init_langfuse()

            assert result is False
            assert is_langfuse_available() is False

    def test_init_with_empty_credentials(self):
        """Test that empty credentials result in disabled Langfuse."""
        with patch.dict(
            os.environ,
            {"LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""},
        ):
            import lineage_server.langfuse_connection_manager as lcm

            lcm._langfuse_available = False
            lcm._langfuse_error = None

            result = init_langfuse()

            assert result is False
            assert is_langfuse_available() is False

    def test_init_with_valid_credentials_but_connection_fails(self):
        """Test handling when credentials are valid but connection fails."""
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-lf-valid-key",
                "LANGFUSE_SECRET_KEY": "sk-lf-valid-key",
                "LANGFUSE_HOST": "https://cloud.langfuse.com",
            },
        ):
            # Mock get_client to raise an exception
            mock_client = MagicMock()
            mock_client.auth_check.side_effect = Exception("Connection refused")

            with patch(
                "lineage_server.langfuse_connection_manager.get_client",
                return_value=mock_client,
            ):
                import lineage_server.langfuse_connection_manager as lcm

                lcm._langfuse_available = False
                lcm._langfuse_error = None

                result = init_langfuse()

                assert result is False
                assert is_langfuse_available() is False
                status = get_langfuse_status()
                assert "Connection refused" in status["langfuse_error"]

    def test_init_with_valid_credentials_and_connection_succeeds(self):
        """Test successful Langfuse initialization."""
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-lf-valid-key",
                "LANGFUSE_SECRET_KEY": "sk-lf-valid-key",
                "LANGFUSE_HOST": "https://cloud.langfuse.com",
            },
        ):
            # Mock get_client to succeed
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True

            with patch(
                "lineage_server.langfuse_connection_manager.get_client",
                return_value=mock_client,
            ):
                import lineage_server.langfuse_connection_manager as lcm

                lcm._langfuse_available = False
                lcm._langfuse_error = None

                result = init_langfuse()

                assert result is True
                assert is_langfuse_available() is True
                status = get_langfuse_status()
                assert status["langfuse_available"] is True
                assert status["langfuse_error"] is None


class TestStatusFunctions:
    """Test cases for status-related functions."""

    def test_is_langfuse_available_returns_boolean(self):
        """Test that is_langfuse_available returns a boolean."""
        result = is_langfuse_available()
        assert isinstance(result, bool)

    def test_get_langfuse_status_returns_dict(self):
        """Test that get_langfuse_status returns a dict with expected keys."""
        status = get_langfuse_status()

        assert isinstance(status, dict)
        assert "langfuse_available" in status
        assert "langfuse_error" in status

    def test_get_langfuse_status_when_disabled(self, mock_langfuse_disabled):
        """Test status dict when Langfuse is disabled."""
        status = get_langfuse_status()

        assert status["langfuse_available"] is False
        assert status["langfuse_error"] is not None

    def test_get_langfuse_status_when_enabled(self, mock_langfuse_enabled):
        """Test status dict when Langfuse is enabled."""
        status = get_langfuse_status()

        assert status["langfuse_available"] is True
        assert status["langfuse_error"] is None
