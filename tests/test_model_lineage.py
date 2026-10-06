"""Tests for the generate_model_lineage tool."""

import pytest

from rca_server.tools.model_lineage import generate_model_lineage


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

    @pytest.mark.asyncio
    async def test_invalid_data_product(self, patched_manifests_path):
        """Test error handling for invalid data product."""
        result = await generate_model_lineage(
            data_product="nonexistent_project", model_name="some_model"
        )

        assert result["success"] is False
        assert result["error"] == "Invalid data product"
        assert "available_data_products" in result
