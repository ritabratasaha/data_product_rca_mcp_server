"""Tests for the generate_model_lineage tool."""

import pytest

from lineage_server.tools.model_lineage import generate_model_lineage


class TestGenerateModelLineage:
    """Test cases for the generate_model_lineage tool."""

    @pytest.mark.asyncio
    async def test_model_with_upstream_dependencies(self, patched_manifests_path):
        """Test tracing lineage for a model with upstream dependencies."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="mart_orders"
        )

        assert result["success"] is True
        assert result["data_product"] == "test_project"
        assert result["model_name"] == "mart_orders"
        assert result["model_id"] == "model.test_project.mart_orders"

        # Should have 2 upstream: stg_orders and source.orders
        assert result["lineage_count"] == 2
        assert len(result["lineage"]) == 2

        # Check lineage structure
        lineage_names = [node["node_name"] for node in result["lineage"]]
        assert "stg_orders" in lineage_names
        assert "orders" in lineage_names

        # Check levels
        levels = {node["node_name"]: node["level"] for node in result["lineage"]}
        assert levels["stg_orders"] == 1
        assert levels["orders"] == 2

    @pytest.mark.asyncio
    async def test_model_with_no_dependencies(self, patched_manifests_path):
        """Test a model that has no upstream dependencies."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="standalone_model"
        )

        assert result["success"] is True
        assert result["model_name"] == "standalone_model"
        assert result["lineage_count"] == 0
        assert result["lineage"] == []
        assert "0 upstream dependencies" in result["message"]

    @pytest.mark.asyncio
    async def test_max_depth_parameter(self, patched_manifests_path):
        """Test that max_depth limits the lineage traversal."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="mart_orders", max_depth=1
        )

        assert result["success"] is True
        # With max_depth=1, should only get immediate dependencies (stg_orders)
        assert result["lineage_count"] == 1
        assert result["lineage"][0]["node_name"] == "stg_orders"
        assert result["lineage"][0]["level"] == 1

    @pytest.mark.asyncio
    async def test_invalid_data_product(self, patched_manifests_path):
        """Test error handling for invalid data product."""
        result = await generate_model_lineage(
            data_product="nonexistent_project", model_name="some_model"
        )

        assert result["success"] is False
        assert result["error"] == "Data product not found"
        assert "available_data_products" in result

    @pytest.mark.asyncio
    async def test_invalid_model(self, patched_manifests_path):
        """Test error handling for invalid model name."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="nonexistent_model"
        )

        assert result["success"] is False
        assert result["error"] == "Model not found"
        assert "available_models" in result
        assert "mart_orders" in result["available_models"]

    @pytest.mark.asyncio
    async def test_case_insensitive_model_name(self, patched_manifests_path):
        """Test that model name matching is case-insensitive."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="MART_ORDERS"
        )

        assert result["success"] is True
        assert result["model_name"] == "mart_orders"

    @pytest.mark.asyncio
    async def test_lineage_includes_resource_types(self, patched_manifests_path):
        """Test that lineage includes resource type information."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="mart_orders"
        )

        assert result["success"] is True

        resource_types = {
            node["node_name"]: node["resource_type"] for node in result["lineage"]
        }
        assert resource_types["stg_orders"] == "model"
        assert resource_types["orders"] == "source"

    @pytest.mark.asyncio
    async def test_lineage_includes_schema_info(self, patched_manifests_path):
        """Test that lineage includes database and schema information."""
        result = await generate_model_lineage(
            data_product="test_project", model_name="mart_orders"
        )

        assert result["success"] is True

        for node in result["lineage"]:
            assert "database" in node
            assert "schema" in node
            assert node["database"] == "postgres"
