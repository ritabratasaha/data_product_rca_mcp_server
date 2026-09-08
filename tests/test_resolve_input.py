"""Tests for the resolve_input tool."""

import pytest

from lineage_server.tools.resolve_input import resolve_input


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
        assert "Validation passed" in result["message"]

    @pytest.mark.asyncio
    async def test_valid_data_product_model_and_column(self, patched_manifests_path):
        """Test successful validation with data product, model, and column."""
        result = await resolve_input(
            data_product="test_project",
            model_name="mart_orders",
            column_name="order_id",
        )

        assert result["success"] is True
        assert result["column_name"] == "order_id"
        assert "order_id" in result["message"]

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

    @pytest.mark.asyncio
    async def test_invalid_model(self, patched_manifests_path):
        """Test that invalid model returns available options."""
        result = await resolve_input(
            data_product="test_project", model_name="nonexistent_model"
        )

        assert result["success"] is False
        assert result["error"] == "Invalid model"
        assert "nonexistent_model" in result["message"]
        assert "available_models" in result
        assert "mart_orders" in result["available_models"]

    @pytest.mark.asyncio
    async def test_invalid_column(self, patched_manifests_path):
        """Test that invalid column returns available options."""
        result = await resolve_input(
            data_product="test_project",
            model_name="mart_orders",
            column_name="nonexistent_column",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid column"
        assert "nonexistent_column" in result["message"]
        assert "available_columns" in result
        assert "order_id" in result["available_columns"]

    @pytest.mark.asyncio
    async def test_case_insensitive_model_matching(self, patched_manifests_path):
        """Test that model name matching is case-insensitive."""
        result = await resolve_input(
            data_product="test_project", model_name="MART_ORDERS"
        )

        assert result["success"] is True
        assert result["model_name"] == "mart_orders"

    @pytest.mark.asyncio
    async def test_case_insensitive_column_matching(self, patched_manifests_path):
        """Test that column name matching is case-insensitive."""
        result = await resolve_input(
            data_product="test_project",
            model_name="mart_orders",
            column_name="ORDER_ID",
        )

        assert result["success"] is True
        assert result["column_name"] == "order_id"

    @pytest.mark.asyncio
    async def test_no_data_products_available(self, tmp_path):
        """Test error when no data products are available."""
        from unittest.mock import patch

        # Patch to an empty directory
        with patch(
            "lineage_server.manifest_utils.MANIFESTS_BASE_PATH", tmp_path
        ), patch("lineage_server.tools.resolve_input.MANIFESTS_BASE_PATH", tmp_path):
            result = await resolve_input(
                data_product="any_project", model_name="any_model"
            )

        assert result["success"] is False
        assert "No data products available" in result["error"]
