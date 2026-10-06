"""Shared pytest fixtures for rca-server tests."""

import os
os.environ["TESTING"] = "1"

from pathlib import Path
from unittest.mock import patch

import pytest

# Path to test fixtures
FIXTURES_PATH = Path(__file__).parent / "fixtures"


@pytest.fixture
def patched_manifests_path():
    """Patch MANIFESTS_BASE_PATH to use test fixtures."""
    with patch("rca_server.manifest_utils.MANIFESTS_BASE_PATH", FIXTURES_PATH):
        yield FIXTURES_PATH


@pytest.fixture
def mock_langfuse_disabled():
    """Mock Langfuse as disabled."""
    with patch("rca_server.langfuse_connection_manager.langfuse_available", False), \
         patch("rca_server.langfuse_connection_manager.langfuse_error", "Langfuse credentials not configured"):
        yield


@pytest.fixture
def mock_langfuse_enabled():
    """Mock Langfuse as enabled."""
    with patch("rca_server.langfuse_connection_manager.langfuse_available", True), \
         patch("rca_server.langfuse_connection_manager.langfuse_error", None):
        yield


@pytest.fixture(autouse=True)
def disable_langfuse_observe():
    """Disable Langfuse @observe decorator during tests."""
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""}):
        yield
