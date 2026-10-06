"""Data retrieval tool using Snowflake."""

import asyncio

import snowflake.connector
import sqlglot
from langfuse import observe

from rca_server.logger import get_logger
from rca_server.snowflake_connection import get_snowflake_connection
from rca_server.tools.validate_db_connection import validate_db_connection

logger = get_logger("get_data")

MAX_ROWS = 10


def _enforce_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
    """
    Use sqlglot to enforce a maximum LIMIT on the query.

    If the query has no LIMIT, adds LIMIT max_rows.
    If the query has a LIMIT > max_rows, caps it at max_rows.
    """
    parsed = sqlglot.parse_one(sql, dialect="snowflake")
    existing_limit = parsed.args.get("limit")

    if existing_limit:
        current = int(existing_limit.expression.this)
        if current > max_rows:
            parsed = parsed.limit(max_rows)
    else:
        parsed = parsed.limit(max_rows)

    return parsed.sql(dialect="snowflake")


@observe()
async def get_data(sql: str) -> dict:
    """
    Execute a read-only SELECT query against Snowflake.

    Returns up to 10 rows. Automatically checks database connectivity
    first using validate_db_connection.

    Args:
        sql: The Snowflake SELECT statement to execute.

    Returns:
        A dict containing:
        - success: Whether the query executed successfully
        - sql: The executed SQL (with LIMIT enforced)
        - row_count: Number of rows returned
        - data: Rows as list of dicts
        - message: Human-readable result
        - error_details: Error description if failed
    """
    sql_display = sql[:200] + "..." if len(sql) > 200 else sql

    # Check DB connection first (reuses retry logic from validate_db_connection)
    db_result = await validate_db_connection()
    if not db_result["success"]:
        logger.warning("Database connection check failed before query execution")
        return {
            "success": False,
            "sql": sql_display,
            "row_count": 0,
            "data": [],
            "message": db_result["message"],
            "error_details": db_result["error_details"],
        }

    limited_sql = _enforce_limit(sql)
    limited_display = limited_sql[:200] + "..." if len(limited_sql) > 200 else limited_sql

    try:
        logger.debug("Connecting to Snowflake for query execution")

        def _execute_query(sql_to_run: str):
            conn = get_snowflake_connection()
            cur = conn.cursor(snowflake.connector.DictCursor)
            cur.execute(sql_to_run)
            data = cur.fetchall()
            cur.close()
            conn.close()
            return data

        data = await asyncio.to_thread(_execute_query, limited_sql)

        logger.info(f"Query returned {len(data)} rows")
        return {
            "success": True,
            "sql": limited_display,
            "row_count": len(data),
            "data": data,
            "message": f"Query returned {len(data)} row(s)",
            "error_details": None,
        }

    except Exception as e:
        logger.warning(f"Query execution error: {e}")
        return {
            "success": False,
            "sql": limited_display,
            "row_count": 0,
            "data": [],
            "message": "Query execution failed",
            "error_details": str(e) or f"{type(e).__name__}: query failed",
        }
