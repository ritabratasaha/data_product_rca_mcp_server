"""SQL validation tool using Snowflake."""

import asyncio

import sqlglot
from langfuse import observe

from rca_server.logger import get_logger
from rca_server.snowflake_connection import get_snowflake_connection
from rca_server.tools.validate_db_connection import validate_db_connection

logger = get_logger("validate_sql")


def _check_query_policy(sql: str) -> tuple[bool, str | None]:
    """
    Check SQL is a read-only SELECT with explicit column names.

    Uses sqlglot for safe SQL parsing without execution.
    Rejects non-SELECT statements and SELECT * queries.

    Args:
        sql: The SQL statement to check.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_description).
    """
    try:
        parsed = sqlglot.parse(sql, dialect="snowflake")
        if not parsed:
            return False, "Could not parse SQL"

        for statement in parsed:
            if not isinstance(statement, sqlglot.exp.Select):
                return False, "Only read-only SELECT queries are allowed"
            if statement.find(sqlglot.exp.Star):
                return False, "SELECT * is not allowed. Please specify explicit column names to limit data volume."
        return True, None
    except sqlglot.errors.ParseError as e:
        return False, f"Invalid SQL syntax: {e}"


@observe()
async def validate_sql(sql: str) -> dict:
    """
    Validate read-only SELECT SQL against Snowflake.

    Only SELECT statements are allowed. INSERT, UPDATE, DELETE, DROP,
    and other write operations will be rejected for security.

    Uses sqlglot for safe SQL parsing and Snowflake EXPLAIN for
    schema validation without executing the query.

    Automatically checks database connectivity first using validate_db_connection.

    Args:
        sql: The Snowflake SELECT statement to validate.

    Returns:
        A dict containing:
        - success: Whether the SQL is valid
        - sql: The input SQL (truncated if > 200 chars)
        - message: Human-readable result
        - error_details: Error description if validation failed
    """
    sql_display = sql[:200] + "..." if len(sql) > 200 else sql

    # Check DB connection first (reuses retry logic from validate_db_connection)
    db_result = await validate_db_connection()
    if not db_result["success"]:
        logger.warning("Database connection check failed before SQL validation")
        return {
            "success": False,
            "sql": sql_display,
            "message": db_result["message"],
            "error_details": db_result["error_details"],
        }

    is_readonly, readonly_error = _check_query_policy(sql)
    if not is_readonly:
        logger.warning(f"Query policy violation: {readonly_error}")
        return {
            "success": False,
            "sql": sql_display,
            "message": "SQL validation failed",
            "error_details": readonly_error,
        }

    try:
        logger.debug("Connecting to Snowflake for SQL validation")

        def _validate(sql_to_check: str):
            conn = get_snowflake_connection()
            cur = conn.cursor()
            cur.execute(f"EXPLAIN {sql_to_check}")
            cur.close()
            conn.close()

        await asyncio.to_thread(_validate, sql)

        logger.info("SQL validation successful")
        return {
            "success": True,
            "sql": sql_display,
            "message": "SQL is valid - syntax and schema references verified",
            "error_details": None,
        }

    except Exception as e:
        logger.warning(f"SQL validation error: {e}")
        return {
            "success": False,
            "sql": sql_display,
            "message": "SQL validation failed",
            "error_details": str(e),
        }
