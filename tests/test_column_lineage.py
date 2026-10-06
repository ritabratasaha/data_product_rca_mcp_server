"""Tests for the generate_column_lineage tool."""

import pytest

from rca_server.tools.column_lineage import (
    generate_column_lineage,
    _extract_alias_mapping,
)


class TestExtractAliasMapping:
    """Test cases for the _extract_alias_mapping helper function."""

    def test_simple_alias(self):
        """Test extracting a simple column alias."""
        sql = "SELECT amount AS total_amount FROM orders"
        mapping = _extract_alias_mapping(sql)

        assert mapping.get("total_amount") == "amount"


class TestGenerateColumnLineage:
    """Test cases for the generate_column_lineage tool."""

    @pytest.mark.asyncio
    async def test_column_lineage_traces_upstream(self, patched_manifests_path):
        """Test tracing column lineage through upstream models."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="order_id",
        )

        assert result["success"] is True
        assert result["data_product"] == "test_project"
        assert result["model_name"] == "mart_orders"
        assert result["column_name"] == "order_id"
        assert result["lineage_count"] >= 1

        # Should trace through stg_orders to source
        node_names = [step["node_name"] for step in result["lineage"]]
        assert "mart_orders" in node_names
        assert "stg_orders" in node_names

    @pytest.mark.asyncio
    async def test_column_not_found(self, patched_manifests_path):
        """Test error handling when column doesn't exist."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="nonexistent_column",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid column"
        assert "available_columns" in result
        assert "order_id" in result["available_columns"]

    @pytest.mark.asyncio
    async def test_invalid_data_product(self, patched_manifests_path):
        """Test error handling for invalid data product."""
        result = await generate_column_lineage(
            data_product="nonexistent_project",
            model_name="some_model",
            column_name="some_column",
        )

        assert result["success"] is False
        assert result["error"] == "Invalid data product"
        assert "available_data_products" in result
