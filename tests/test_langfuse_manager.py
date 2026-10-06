"""Tests for the langfuse_connection_manager module."""

import os
from unittest.mock import patch, MagicMock

import pytest

import rca_server.langfuse_connection_manager as lcm
from rca_server.langfuse_connection_manager import (
    init_langfuse,
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
            lcm.langfuse_available = False
            lcm.langfuse_error = None

            result = init_langfuse()

            assert result is False
            assert lcm.langfuse_available is False
            assert "not configured" in lcm.langfuse_error

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
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True

            with patch(
                "rca_server.langfuse_connection_manager.get_client",
                return_value=mock_client,
            ):
                lcm.langfuse_available = False
                lcm.langfuse_error = None

                result = init_langfuse()

                assert result is True
                assert lcm.langfuse_available is True
                assert lcm.langfuse_error is None


class TestGetLangfuseStatus:
    """Test cases for get_langfuse_status function."""

    def test_returns_dict_with_expected_keys(self):
        """Test that get_langfuse_status returns a dict with expected keys."""
        status = get_langfuse_status()

        assert isinstance(status, dict)
        assert "langfuse_available" in status
        assert "langfuse_error" in status
