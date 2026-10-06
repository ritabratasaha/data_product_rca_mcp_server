"""Model lineage tool for dbt manifests."""

import json

from langfuse import observe

from rca_server.logger import get_logger
from rca_server.manifest_utils import get_node, load_slim_manifest
from rca_server.tools.resolve_input import resolve_input

logger = get_logger("model_lineage")


def _trace_upstream(manifest: dict, node_id: str, lineage: list, visited: set, depth: int, max_depth: int | None):
    """Recursively trace upstream dependencies."""
    if node_id in visited:
        return
    if max_depth is not None and depth > max_depth:
        return
    
    visited.add(node_id)
    node = get_node(manifest, node_id)
    if not node:
        return

    lineage.append({
        'node_id': node_id,
        'node_name': node.get('name'),
        'resource_type': node.get('resource_type'),
        'database': node.get('database'),
        'schema': node.get('schema'),
        'description': node.get('description'),
        'level': depth,
    })

    if node.get('resource_type') == 'source':
        return

    upstream_ids = node.get('depends_on', {}).get('nodes', [])
    for upstream_id in upstream_ids:
        _trace_upstream(manifest, upstream_id, lineage, visited, depth + 1, max_depth)


@observe()
async def generate_model_lineage(
    data_product: str,
    model_name: str,
    max_depth: int | None = None
) -> dict:
    """
    Generate model lineage by tracing upstream dependencies.

    Args:
        data_product: Name of the data product (e.g., 'customer_orders', 'flight_information').
        model_name: The name of the model (e.g., 'flight_type').
        max_depth: Maximum depth to traverse (default: None for unlimited).

    Returns:
        A dict containing:
        - success: Whether the operation completed successfully
        - data_product: The data product name
        - model_id: The resolved model ID
        - model_name: The name of the model
        - lineage: List of upstream dependencies
        - lineage_count: Number of upstream nodes
        - message: A human-readable summary

    Raises:
        No exceptions are raised; errors are returned in the response.
    """
    logger.debug(f"generate_model_lineage called: data_product={data_product}, model_name={model_name}, max_depth={max_depth}")
    
    try:
        # Validate inputs via resolve_input (enforced server-side)
        validation = await resolve_input(data_product, model_name)
        if not validation["success"]:
            return validation

        model_id = validation["model_id"]
        resolved_model_name = validation["model_name"]
        manifest = load_slim_manifest(data_product)

        # Trace upstream
        lineage = []
        visited = set()
        _trace_upstream(manifest, model_id, lineage, visited, 0, max_depth)
        
        # Remove the starting model (level 0) from results
        lineage = [n for n in lineage if n['level'] > 0]

        logger.info(f"Model '{resolved_model_name}' has {len(lineage)} upstream dependencies")
        return {
            "success": True,
            "data_product": data_product,
            "model_id": model_id,
            "model_name": resolved_model_name,
            "lineage": lineage,
            "lineage_count": len(lineage),
            "message": f"Model '{resolved_model_name}' has {len(lineage)} upstream dependencies.",
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse manifest file: {str(e)}")
        return {
            "success": False,
            "error": "Invalid JSON",
            "message": f"Failed to parse manifest file: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error while tracing lineage: {str(e)}")
        return {
            "success": False,
            "error": "Unexpected error",
            "message": f"An error occurred while tracing lineage: {str(e)}",
        }
