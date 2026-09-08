"""Shared pytest fixtures for lineage-server tests."""

# Set TESTING environment variable BEFORE any other imports
# This must be at the very top of conftest.py
import os
os.environ["TESTING"] = "1"

# pytest hook to ensure TESTING is set before collection
def pytest_configure(config):
    """Set TESTING env var before test collection."""
    os.environ["TESTING"] = "1"

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_manifest():
    """Create a sample dbt manifest structure for testing."""
    return {
        "nodes": {
            "model.test_project.mart_orders": {
                "unique_id": "model.test_project.mart_orders",
                "name": "mart_orders",
                "resource_type": "model",
                "database": "postgres",
                "schema": "marts",
                "relation_name": '"postgres"."marts"."mart_orders"',
                "columns": {
                    "order_id": {"name": "order_id", "data_type": "integer"},
                    "customer_id": {"name": "customer_id", "data_type": "integer"},
                    "total_amount": {"name": "total_amount", "data_type": "numeric"},
                },
                "depends_on": {
                    "macros": [],
                    "nodes": ["model.test_project.stg_orders"],
                },
                "description": "Mart table for orders",
                "compiled_code": "SELECT order_id, customer_id, amount AS total_amount FROM stg_orders",
            },
            "model.test_project.stg_orders": {
                "unique_id": "model.test_project.stg_orders",
                "name": "stg_orders",
                "resource_type": "model",
                "database": "postgres",
                "schema": "staging",
                "relation_name": '"postgres"."staging"."stg_orders"',
                "columns": {
                    "order_id": {"name": "order_id", "data_type": "integer"},
                    "customer_id": {"name": "customer_id", "data_type": "integer"},
                    "amount": {"name": "amount", "data_type": "numeric"},
                },
                "depends_on": {
                    "macros": [],
                    "nodes": ["source.test_project.raw.orders"],
                },
                "description": "Staging table for orders",
                "compiled_code": "SELECT order_id, customer_id, amount FROM raw.orders",
            },
            "model.test_project.standalone_model": {
                "unique_id": "model.test_project.standalone_model",
                "name": "standalone_model",
                "resource_type": "model",
                "database": "postgres",
                "schema": "marts",
                "relation_name": '"postgres"."marts"."standalone_model"',
                "columns": {
                    "id": {"name": "id", "data_type": "integer"},
                },
                "depends_on": {
                    "macros": [],
                    "nodes": [],
                },
                "description": "A model with no dependencies",
                "compiled_code": "SELECT 1 AS id",
            },
        },
        "sources": {
            "source.test_project.raw.orders": {
                "unique_id": "source.test_project.raw.orders",
                "name": "orders",
                "resource_type": "source",
                "database": "postgres",
                "schema": "raw",
                "relation_name": '"postgres"."raw"."orders"',
                "columns": {
                    "order_id": {"name": "order_id", "data_type": "integer"},
                    "customer_id": {"name": "customer_id", "data_type": "integer"},
                    "amount": {"name": "amount", "data_type": "numeric"},
                },
                "depends_on": None,
                "description": "Raw orders source",
            },
        },
    }


@pytest.fixture
def mock_manifests_dir(sample_manifest, tmp_path):
    """Create a temporary manifests directory with test data."""
    # Create test_project data product directory
    data_product_dir = tmp_path / "test_project"
    data_product_dir.mkdir()

    # Write manifest.json
    manifest_path = data_product_dir / "manifest.json"
    manifest_path.write_text(json.dumps(sample_manifest, indent=2))

    # Write manifest_slim.json (same structure for tests)
    slim_path = data_product_dir / "manifest_slim.json"
    slim_path.write_text(json.dumps(sample_manifest, indent=2))

    return tmp_path


@pytest.fixture
def patched_manifests_path(mock_manifests_dir):
    """Patch MANIFESTS_BASE_PATH to use mock directory."""
    with patch(
        "lineage_server.manifest_utils.MANIFESTS_BASE_PATH", mock_manifests_dir
    ):
        yield mock_manifests_dir


@pytest.fixture
def mock_langfuse_disabled():
    """Mock Langfuse as disabled for testing."""
    with patch(
        "lineage_server.langfuse_connection_manager._langfuse_available", False
    ), patch(
        "lineage_server.langfuse_connection_manager._langfuse_error",
        "Langfuse credentials not configured",
    ):
        yield


@pytest.fixture
def mock_langfuse_enabled():
    """Mock Langfuse as enabled for testing."""
    with patch(
        "lineage_server.langfuse_connection_manager._langfuse_available", True
    ), patch("lineage_server.langfuse_connection_manager._langfuse_error", None):
        yield


@pytest.fixture(autouse=True)
def disable_langfuse_observe():
    """Disable Langfuse @observe decorator during tests."""
    # The @observe decorator should be a no-op when credentials aren't configured
    # But we'll ensure it doesn't cause issues by mocking the environment
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""}):
        yield
