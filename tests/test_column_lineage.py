"""Tests for the generate_column_lineage tool."""

import pytest

from lineage_server.tools.column_lineage import (
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

    def test_multiple_aliases(self):
        """Test extracting multiple column aliases."""
        sql = "SELECT id AS order_id, amt AS amount, stat AS status FROM orders"
        mapping = _extract_alias_mapping(sql)

        assert mapping.get("order_id") == "id"
        assert mapping.get("amount") == "amt"
        assert mapping.get("status") == "stat"

    def test_no_aliases(self):
        """Test SQL with no aliases returns empty mapping."""
        sql = "SELECT id, amount, status FROM orders"
        mapping = _extract_alias_mapping(sql)

        assert mapping == {}

    def test_empty_sql(self):
        """Test empty SQL returns empty mapping."""
        mapping = _extract_alias_mapping("")
        assert mapping == {}

    def test_none_sql(self):
        """Test None SQL returns empty mapping."""
        mapping = _extract_alias_mapping(None)
        assert mapping == {}


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
    async def test_column_lineage_includes_levels(self, patched_manifests_path):
        """Test that lineage steps include level information."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="order_id",
        )

        assert result["success"] is True

        for step in result["lineage"]:
            assert "level" in step
            assert isinstance(step["level"], int)
            assert step["level"] >= 1

    @pytest.mark.asyncio
    async def test_column_not_found(self, patched_manifests_path):
        """Test error handling when column doesn't exist."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="nonexistent_column",
        )

        assert result["success"] is False
        assert result["error"] == "Column not found"
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
        assert result["error"] == "Data product not found"
        assert "available_data_products" in result

    @pytest.mark.asyncio
    async def test_invalid_model(self, patched_manifests_path):
        """Test error handling for invalid model name."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="nonexistent_model",
            column_name="some_column",
        )

        assert result["success"] is False
        assert result["error"] == "Model not found"
        assert "available_models" in result

    @pytest.mark.asyncio
    async def test_column_with_alias_detection(self, patched_manifests_path):
        """Test that alias detection works for column tracing."""
        # In the fixture, mart_orders has compiled_code with "amount AS total_amount"
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="total_amount",
        )

        assert result["success"] is True
        # Should find lineage for the aliased column

    @pytest.mark.asyncio
    async def test_case_insensitive_column_matching(self, patched_manifests_path):
        """Test that column matching is case-insensitive."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="ORDER_ID",
        )

        # Should still find the column despite case mismatch
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_lineage_includes_compiled_code(self, patched_manifests_path):
        """Test that lineage includes compiled SQL code."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="order_id",
        )

        assert result["success"] is True

        for step in result["lineage"]:
            # compiled_code should be present (may be None for sources)
            assert "compiled_code" in step

    @pytest.mark.asyncio
    async def test_lineage_includes_resource_type(self, patched_manifests_path):
        """Test that lineage includes resource type for each step."""
        result = await generate_column_lineage(
            data_product="test_project",
            model_name="mart_orders",
            column_name="order_id",
        )

        assert result["success"] is True

        for step in result["lineage"]:
            assert "resource_type" in step
            assert step["resource_type"] in ("model", "source", "seed", "snapshot")
