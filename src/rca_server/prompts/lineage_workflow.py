"""Lineage workflow prompt for AI agents."""

from rca_server.manifest_utils import load_data_product_config


def lineage_workflow_instructions() -> str:
    """
    Instructions for AI agents on how to use the lineage tools.
    
    This prompt should be read by AI agents before using lineage tools.
    """
    config = load_data_product_config()
    mapping_lines = []
    for name, info in config.items():
        db = info.get("database_name", "N/A")
        dag = info.get("airflow_dag_name", "N/A")
        mapping_lines.append(f"- **{name}**: database=`{db}`, airflow_dag=`{dag}`")

    mapping_section = (
        "\n\n### Data Product Mapping:\n" + "\n".join(mapping_lines)
        if mapping_lines else ""
    )

    return """
## Lineage Server Tool Usage Instructions

When a user requests lineage information, follow this workflow:

### If the user explicitly requests a specific tool:
- Use that tool directly (e.g., "use generate_model_lineage for X")

### Important: Never assume data_product
- If the user does not explicitly provide a data_product name, **do NOT guess or infer it** from conversation context.
- Instead, ask the user which data product they mean, or call `resolve_input` without a data_product to get the list of available data products.
- Only proceed once the user has confirmed the data_product.

### For general lineage requests:
1. First call `resolve_input` to validate the data_product, model_name, and column_name
2. If validation succeeds: Call the appropriate lineage tool
   - For column lineage: `generate_column_lineage`
   - For model lineage: `generate_model_lineage`
3. Present the lineage results to the user
4. **After lineage is generated**: If the lineage includes `compiled_code`, 
   offer to validate the SQL using the SQL validation workflow below
5. If validation fails: Report the error and show available options

### For SQL validation requests:
1. Call `validate_db_connection` to check database availability
2. If connection is up: Call `validate_sql` with the SQL
3. If connection fails: Report that the database is unavailable

### For data retrieval requests:
1. Call `validate_db_connection` to check database availability
2. If connection is up: Call `validate_sql` to validate the SQL first
3. If SQL is valid: Call `get_data` with the SQL (max 10 rows returned)
4. If any step fails: Report the error and stop

### Available Tools:
- `ping`: Test server connectivity
- `resolve_input`: Validate inputs before lineage operations
- `generate_column_lineage`: Trace a column through upstream models
- `generate_model_lineage`: Trace model dependencies upstream
- `validate_db_connection`: Test if the Snowflake database is reachable
- `validate_sql`: Validate SQL syntax and schema references against the database
- `get_data`: Execute a read-only SELECT query and return up to 10 rows
- `get_airflow_dag_runs`: Get Airflow DAG run details for a specific date

### Example Workflow:
User: "What is the lineage of the bookings model in flight_information?"

1. Call resolve_input(data_product="flight_information", model_name="bookings")
2. If success: Call generate_model_lineage(data_product="flight_information", model_name="bookings")
3. Present the lineage results to the user
4. If user wants to validate SQL:
   a. Call validate_db_connection() to check database is up
   b. If up: Call validate_sql with the compiled_code from lineage

User: "Get me 5 rows from bookings.segments"

1. Call validate_db_connection() to check database is up
2. If up: Call validate_sql("SELECT * FROM bookings.segments LIMIT 5")
3. If valid: Call get_data("SELECT * FROM bookings.segments LIMIT 5")
4. Present the data to the user

### For Airflow DAG queries:
1. Call `get_airflow_dag_runs` with the DAG ID and date (YYYY-MM-DD)
2. The tool checks Airflow connectivity first, then fetches run details
3. Returns: run count, status/duration per run, 7-day avg duration, and task logs

User: "How did the etl_bookings DAG perform on 2026-09-20?"

1. Call get_airflow_dag_runs(dag_id="etl_bookings", date="2026-09-20")
2. Present the run count, statuses, durations, and any failures from the logs

### SQL Validation:
The `validate_sql` tool checks SQL against the configured Snowflake database:
- Validates syntax correctness
- Verifies table and column references exist
- Does NOT execute the query or retrieve data
- Returns detailed error information if validation fails
""" + mapping_section
