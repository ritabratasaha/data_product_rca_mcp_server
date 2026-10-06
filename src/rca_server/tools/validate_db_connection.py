"""Database connection validation tool for Snowflake."""

import asyncio
import os

from langfuse import observe

from rca_server.logger import get_logger
from rca_server.snowflake_connection import get_snowflake_connection

logger = get_logger("validate_db_connection")


@observe()
async def validate_db_connection() -> dict:
    """
    Validate if the Snowflake database is up and running.

    Executes SELECT CURRENT_TIMESTAMP() to test connectivity.
    Retries once after 5 seconds if the first attempt fails.

    Returns:
        A dict containing:
        - success: Whether the database is reachable
        - message: Human-readable result
        - server_time: Database server time if connected
        - error_details: Error description if connection failed
    """
    account = os.getenv("SNOWFLAKE_ACCOUNT")

    if not account:
        logger.warning("Snowflake account not configured")
        return {
            "success": False,
            "message": "Database connection check failed",
            "server_time": None,
            "error_details": "SNOWFLAKE_ACCOUNT not configured",
        }

    last_error = None

    for attempt in [1, 2]:
        try:
            logger.debug(f"Connection attempt {attempt}")

            def _connect():
                conn = get_snowflake_connection()
                cur = conn.cursor()
                cur.execute("SELECT CURRENT_TIMESTAMP()")
                server_time = cur.fetchone()[0]
                cur.close()
                conn.close()
                return str(server_time)

            server_time = await asyncio.to_thread(_connect)

            logger.info(f"Database connection successful on attempt {attempt}")
            return {
                "success": True,
                "message": "Database is up and running",
                "server_time": server_time,
                "error_details": None,
            }

        except Exception as e:
            last_error = e

            if attempt == 1:
                logger.warning(f"Connection attempt 1 failed, retrying in 5s: {e}")
                await asyncio.sleep(5)
            else:
                logger.error(f"Connection attempt 2 failed: {e}")

    return {
        "success": False,
        "message": "Database connection check failed after 2 attempts",
        "server_time": None,
        "error_details": str(last_error) or f"{type(last_error).__name__}: connection failed",
    }
