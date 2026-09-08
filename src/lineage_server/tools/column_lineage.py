"""Column lineage tool for dbt manifests."""

import json
import re

from langfuse import observe
from sqlglot import parse_one, exp

from lineage_server.logger import get_logger
from lineage_server.manifest_utils import (
    get_node,
    get_models_with_columns,
    list_data_products,
    load_slim_manifest,
    _get_original_manifest_path,
)

logger = get_logger("column_lineage")


def _extract_alias_mapping(sql: str) -> dict[str, str]:
    """
    Extract column alias mappings from SQL.

    Parses the SQL to find SELECT expressions with aliases and maps
    the alias name to the source column name.

    Args:
        sql: The compiled SQL code to parse.

    Returns:
        Dict mapping alias_name (lowercase) -> source_column_name (lowercase)
        e.g., {'flight_status': 'status', 'total': 'amount'}
    """
    if not sql:
        return {}

    mapping = {}
    try:
        parsed = parse_one(sql)
        for select in parsed.find_all(exp.Select):
            for projection in select.expressions:
                alias = projection.alias
                if alias:
                    # Find source columns in this expression
                    for col in projection.find_all(exp.Column):
                        source_col = col.name
                        mapping[alias.lower()] = source_col.lower()
                        break  # Take first column as source
    except Exception:
        pass  # Fall back to no mapping on parse errors

    return mapping


def _get_upstream_nodes(manifest: dict, node_id: str) -> list[str]:
    """Get immediate upstream node IDs for a given node."""
    node = manifest['nodes'].get(node_id)
    if node:
        return node.get('depends_on', {}).get('nodes', [])
    return []


def _expand_select_star(sql: str | None, columns: list[str]) -> str | None:
    """Replace SELECT * with the actual column list."""
    if not sql or not columns:
        return sql
    col_list = ',\n    '.join(columns)
    expanded = re.sub(r'(?i)(select\s+)\*', rf'\1{col_list}', sql)
    return expanded


def _trace(manifest: dict, node_id: str, col_name: str, lineage: list, visited: set, source_col: str | None = None):
    """
    Recursively trace a column through upstream nodes.

    Args:
        manifest: The loaded manifest dict.
        node_id: The current node ID to trace.
        col_name: The column name being traced (may change through aliases).
        lineage: List to append lineage steps to.
        visited: Set of already visited node IDs.
        source_col: The original source column name if alias resolution was used.
    """
    if node_id in visited:
        return
    visited.add(node_id)

    node = get_node(manifest, node_id)
    if not node:
        return

    is_source = node.get('resource_type') == 'source'
    columns = list(node.get('columns', {}).keys())
    compiled_code = node.get('compiled_code', '')

    if compiled_code:
        compiled_code = _expand_select_star(compiled_code, columns)

    lineage.append({
        'node_id': node_id,
        'node_name': node.get('name'),
        'resource_type': node.get('resource_type'),
        'column': col_name,
        'source_column': source_col if source_col and source_col.lower() != col_name.lower() else None,
        'compiled_code': compiled_code
    })

    if is_source:
        return

    # Extract alias mapping from current node's SQL
    alias_map = _extract_alias_mapping(compiled_code) if compiled_code else {}

    for upstream_id in _get_upstream_nodes(manifest, node_id):
        upstream_node = get_node(manifest, upstream_id)
        if upstream_node:
            upstream_cols = upstream_node.get('columns', {})
            upstream_cols_lower = [c.lower() for c in upstream_cols.keys()]
            is_upstream_source = upstream_node.get('resource_type') == 'source'

            # Check direct match
            has_column = col_name.lower() in upstream_cols_lower

            if has_column or is_upstream_source:
                _trace(manifest, upstream_id, col_name, lineage, visited)
            else:
                # Try alias resolution - check if current column is an alias
                resolved_col = alias_map.get(col_name.lower())
                if resolved_col and resolved_col in upstream_cols_lower:
                    logger.debug(f"Alias resolved: {col_name} -> {resolved_col}")
                    _trace(manifest, upstream_id, resolved_col, lineage, visited, source_col=col_name)


@observe()
async def generate_column_lineage(
    data_product: str,
    model_name: str,
    column_name: str
) -> dict:
    """
    Generate column lineage by tracing a column through upstream models and sources.

    Args:
        data_product: Name of the data product (e.g., 'customer_orders', 'flight_information').
        model_name: The name of the model (e.g., 'flight_type').
        column_name: The name of the column to trace.

    Returns:
        A dict containing:
        - success: Whether the operation completed successfully
        - data_product: The data product name
        - model_id: The resolved model ID
        - model_name: The model name that was traced
        - column_name: The column that was traced
        - lineage: List of lineage steps from target model to source
        - lineage_count: Number of steps in the lineage
        - message: A human-readable summary

    Raises:
        No exceptions are raised; errors are returned in the response.
    """
    logger.debug(f"generate_column_lineage called: data_product={data_product}, model_name={model_name}, column_name={column_name}")
    
    try:
        manifest_path = _get_original_manifest_path(data_product)
        
        if not manifest_path.exists():
            available_products = list_data_products()
            logger.warning(f"Data product not found: {data_product}")
            return {
                "success": False,
                "error": "Data product not found",
                "message": f"Manifest not found for data product '{data_product}' at: {manifest_path}",
                "available_data_products": available_products,
            }

        manifest = load_slim_manifest(data_product)

        # Resolve model_name to model_id
        models = get_models_with_columns(manifest)
        model_match = None
        resolved_model_name = None
        for name, info in models.items():
            if name.lower() == model_name.lower():
                model_match = info
                resolved_model_name = name
                break

        if not model_match:
            logger.warning(f"Model not found: {model_name}")
            return {
                "success": False,
                "error": "Model not found",
                "message": f"Model '{model_name}' not found in data product '{data_product}'.",
                "available_models": list(models.keys()),
            }

        model_id = model_match['model_id']
        node = get_node(manifest, model_id)

        columns = list(node.get('columns', {}).keys())
        if column_name.lower() not in [c.lower() for c in columns]:
            logger.warning(f"Column not found: {column_name} in model {resolved_model_name}")
            return {
                "success": False,
                "error": "Column not found",
                "message": f"Column '{column_name}' not found in model '{resolved_model_name}'.",
                "available_columns": columns,
            }

        lineage = []
        visited = set()
        _trace(manifest, model_id, column_name, lineage, visited)

        # Add level to each lineage item
        for i, step in enumerate(lineage):
            step['level'] = i + 1

        logger.info(f"Successfully traced column '{column_name}' through {len(lineage)} nodes")
        return {
            "success": True,
            "data_product": data_product,
            "model_id": model_id,
            "model_name": resolved_model_name,
            "column_name": column_name,
            "lineage": lineage,
            "lineage_count": len(lineage),
            "message": f"Successfully traced column '{column_name}' in '{data_product}' through {len(lineage)} nodes.",
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
