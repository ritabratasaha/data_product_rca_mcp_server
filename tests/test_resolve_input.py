"""Tests for the resolve_input tool."""

import pytest

from rca_server.tools.resolve_input import resolve_input


class TestResolveInput:
    """Test cases for the resolve_input tool."""

    @pytest.mark.asyncio
    async def test_valid_data_product_and_model(self, patched_manifests_path):
        """Test successful validation with valid data product and model."""
        result = await resolve_input(
            data_product="test_project", model_name="mart_orders"
        )

        assert result["success"] is True
        assert result["data_product"] == "test_project"
        assert result["model_name"] == "mart_orders"
        assert result["model_id"] == "model.test_project.mart_orders"
        assert result["column_name"] is None
        assert result["database_name"] is None
        assert result["airflow_dag_name"] is None
        assert "Validation passed" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_data_product(self, patched_manifests_path):
        """Test that invalid data product returns available options."""
        result = await resolve_input(
            data_product="nonexistent_project", model_name="some_model"
        )

        assert result["success"] is False
        assert result["error"] == "Invalid data product"
        assert "nonexistent_project" in result["message"]
        assert "available_data_products" in result
        assert "test_project" in result["available_data_products"]
