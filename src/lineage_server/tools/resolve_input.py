"""Resolve input tool for validating lineage query parameters."""

import json

from langfuse import observe

from lineage_server.logger import get_logger
from lineage_server.manifest_utils import (
    MANIFESTS_BASE_PATH,
    get_models_with_columns,
    list_data_products,
    load_slim_manifest,
)

logger = get_logger("resolve_input")


@observe()
async def resolve_input(
    data_product: str,
    model_name: str,
    column_name: str | None = None
) -> dict:
    """
    Validate data_product, model_name, and optional column_name before lineage operations.

    Use this tool to validate user input before calling generate_column_lineage or
    generate_model_lineage. It checks that the specified data product, model, and
    column (if provided) exist in the manifest.

    Args:
        data_product: Name of the data product (e.g., 'flight_information').
        model_name: Name of the model (e.g., 'flight_type').
        column_name: Optional column name to validate (e.g., 'flight_status').

    Returns:
        A dict containing:
        - success: Whether the validation passed
        - data_product: The validated data product name
        - model_id: The full model ID (e.g., 'model.project.model_name')
        - model_name: The validated model name
        - column_name: The validated column name (None if not provided)
        - message: A human-readable summary
    """
    logger.debug(f"resolve_input called: data_product={data_product}, model_name={model_name}, column_name={column_name}")

    try:
        # 1. Validate data_product exists
        data_products = list_data_products()

        if not data_products:
            logger.warning("No data products found")
            return {
                "success": False,
                "error": "No data products available",
                "message": f"No manifest files found in {MANIFESTS_BASE_PATH}",
            }

        if data_product not in data_products:
            logger.warning(f"Invalid data product: {data_product}")
            return {
                "success": False,
                "error": "Invalid data product",
                "message": f"Data product '{data_product}' not found.",
                "available_data_products": data_products,
            }

        # 2. Load manifest and validate model exists
        manifest = load_slim_manifest(data_product)
        models = get_models_with_columns(manifest)

        if not models:
            logger.warning(f"No models found in data product: {data_product}")
            return {
                "success": False,
                "error": "No models found",
                "message": f"No models found in data product '{data_product}'.",
            }

        # Case-insensitive model lookup
        model_match = None
        for name in models.keys():
            if name.lower() == model_name.lower():
                model_match = name
                break

        if not model_match:
            logger.warning(f"Invalid model: {model_name}")
            return {
                "success": False,
                "error": "Invalid model",
                "message": f"Model '{model_name}' not found in data product '{data_product}'.",
                "available_models": list(models.keys()),
            }

        model_info = models[model_match]
        model_id = model_info['model_id']
        columns = model_info['columns']

        # 3. If column_name provided, validate it exists (strict)
        validated_column = None
        if column_name:
            columns_lower = {c.lower(): c for c in columns}
            if column_name.lower() not in columns_lower:
                logger.warning(f"Invalid column: {column_name}")
                return {
                    "success": False,
                    "error": "Invalid column",
                    "message": f"Column '{column_name}' not found in model '{model_match}'.",
                    "available_columns": columns,
                }
            validated_column = columns_lower[column_name.lower()]

        # 4. Return success with validated values
        logger.info(f"Successfully validated: data_product={data_product}, model={model_match}, column={validated_column}")

        return {
            "success": True,
            "data_product": data_product,
            "model_id": model_id,
            "model_name": model_match,
            "column_name": validated_column,
            "message": f"Validation passed. Model '{model_match}' in '{data_product}'" +
                      (f" with column '{validated_column}'." if validated_column else "."),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse manifest: {str(e)}")
        return {
            "success": False,
            "error": "Invalid JSON",
            "message": f"Failed to parse manifest file: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": "Unexpected error",
            "message": f"An error occurred while validating input: {str(e)}",
        }
