"""Shared utilities for loading and processing dbt manifests."""

import json
import os
from pathlib import Path

from rca_server.logger import get_logger

logger = get_logger("manifest_utils")

# Base path for manifests
# Use MANIFESTS_PATH env var if set, otherwise calculate relative to source
_default_path = Path(__file__).parent.parent.parent / "manifests"
MANIFESTS_BASE_PATH = Path(os.getenv("MANIFESTS_PATH", str(_default_path)))

# Unified attributes to keep in slim manifest
SLIM_ATTRS = [
    'unique_id', 'name', 'resource_type', 'database', 'schema',
    'relation_name', 'columns', 'depends_on', 'description',
    'compiled_code'
]


def _get_original_manifest_path(data_product: str) -> Path:
    """Get path to the original manifest.json."""
    return MANIFESTS_BASE_PATH / data_product / "manifest.json"


def get_slim_manifest_path(data_product: str) -> Path:
    """Get path to the slim manifest_slim.json."""
    return MANIFESTS_BASE_PATH / data_product / "manifest_slim.json"


def list_data_products() -> list[str]:
    """List all available data products from the manifests directory."""
    if not MANIFESTS_BASE_PATH.exists():
        return []
    return [
        p.name for p in MANIFESTS_BASE_PATH.iterdir()
        if p.is_dir() and (p / "manifest.json").exists()
    ]


def _extract_slim_node(item: dict) -> dict:
    """Extract slim attributes from a node or source."""
    result = {k: item.get(k) for k in SLIM_ATTRS}
    if cols := result.get('columns'):
        result['columns'] = {
            k: {'name': v.get('name'), 'data_type': v.get('data_type')}
            for k, v in cols.items()
        }
    return result


def _create_slim_manifest(data_product: str) -> None:
    """Create manifest_slim.json from manifest.json."""
    original_path = _get_original_manifest_path(data_product)
    slim_path = get_slim_manifest_path(data_product)
    
    logger.debug(f"Creating slim manifest for {data_product}")
    
    with open(original_path) as f:
        manifest = json.load(f)
    
    nodes = {
        k: _extract_slim_node(v)
        for k, v in manifest.get('nodes', {}).items()
        if v.get('resource_type') in ('model', 'seed', 'snapshot')
    }
    sources = {
        k: _extract_slim_node(v)
        for k, v in manifest.get('sources', {}).items()
    }
    
    slim_manifest = {
        'nodes': nodes,
        'sources': sources,
    }
    
    with open(slim_path, 'w') as f:
        json.dump(slim_manifest, f, indent=2)
    
    logger.info(f"Created slim manifest: {slim_path}")


def ensure_slim_manifest(data_product: str) -> None:
    """
    Ensure manifest_slim.json exists and is up-to-date.

    This function checks if the slim manifest needs to be created or regenerated:
    1. If manifest_slim.json doesn't exist, create it from manifest.json
    2. If manifest.json is newer than manifest_slim.json, regenerate the slim version

    The slim manifest contains only the attributes defined in SLIM_ATTRS,
    reducing file size and improving load performance for lineage operations.

    """
    original = _get_original_manifest_path(data_product)
    slim = get_slim_manifest_path(data_product)
    
    if not original.exists():
        raise FileNotFoundError(f"Original manifest not found: {original}")
    
    needs_update = not slim.exists() or original.stat().st_mtime > slim.stat().st_mtime
    
    if needs_update:
        _create_slim_manifest(data_product)


def load_slim_manifest(data_product: str) -> dict:
    """
    Load the slim manifest for a data product.
    
    Auto-generates manifest_slim.json if it doesn't exist or is outdated.

    Args:
        data_product: Name of the data product.

    Returns:
        A dict with 'nodes' and 'sources'.

    Raises:
        FileNotFoundError: If original manifest doesn't exist.
        json.JSONDecodeError: If manifest is invalid JSON.
    """
    ensure_slim_manifest(data_product)
    
    with open(get_slim_manifest_path(data_product)) as f:
        return json.load(f)


def get_node(manifest: dict, node_id: str) -> dict | None:
    """Get a node from either nodes or sources."""
    return manifest['nodes'].get(node_id) or manifest['sources'].get(node_id)


_DATA_PRODUCTS_CONFIG_FILE = "data_products.json"


def load_data_product_config() -> dict:
    """Load the data product mapping from data_products.json.

    Returns a dict mapping each data product name to its corresponding
    database name and Airflow DAG name.
    """
    config_path = MANIFESTS_BASE_PATH / _DATA_PRODUCTS_CONFIG_FILE
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def get_data_product_info(data_product: str) -> dict | None:
    """Get config for a single data product (database_name, airflow_dag_name)."""
    config = load_data_product_config()
    return config.get(data_product)


def get_models_with_columns(manifest: dict) -> dict[str, dict]:
    """
    Extract models with their IDs and columns from a loaded manifest.

    Returns:
        Dict mapping model_name to {'model_id': str, 'columns': list[str]}
    """
    models = {}
    for node_id, node in manifest.get('nodes', {}).items():
        if node.get('resource_type') in ('model', 'seed', 'snapshot'):
            model_name = node.get('name', '')
            columns = list(node.get('columns', {}).keys())
            models[model_name] = {
                'model_id': node_id,
                'columns': columns
            }
    return models
