"""
SQL Validation Evaluation Tests

Tests for SQL validation workflow including:
- Database connection verification
- Valid SQL validation
- Invalid SQL rejection
- SELECT * rejection
"""

from mcp_eval import task, Expect, with_agent


@task("Test SQL validation workflow")
@with_agent("default")
async def test_sql_validation(agent, session):
    """Verify that valid SQL passes validation after checking database connection."""
    response = await agent.generate_str(
        "Validate this SQL: SELECT TABLE_NAME, TABLE_SCHEMA FROM FLIGHT_ANALYTICS.INFORMATION_SCHEMA.TABLES LIMIT 5"
    )
    
    # Verify validate_sql was called
    await session.assert_that(
        Expect.tools.was_called("validate_sql"),
        name="validate_sql_called"
    )
    
    # Verify response indicates success
    await session.assert_that(
        Expect.content.contains("valid"),
        response=response,
        name="sql_is_valid"
    )


@task("Test invalid SQL is rejected")
@with_agent("default")
async def test_invalid_sql(agent, session):
    """Verify that invalid SQL (nonexistent table) is rejected with error details."""
    response = await agent.generate_str(
        "Validate this SQL: SELECT * FROM nonexistent_table"
    )
    
    # Verify validate_sql was called
    await session.assert_that(
        Expect.tools.was_called("validate_sql"),
        name="validate_sql_called"
    )
    
    # Verify response indicates an error
    await session.assert_that(
        Expect.content.regex(r"(?i)(error|fail|invalid|not found|does not exist)"),
        response=response,
        name="error_returned"
    )


@task("Test SELECT * is rejected")
@with_agent("default")
async def test_select_star_rejected(agent, session):
    """Verify that SELECT * queries are rejected for security."""
    response = await agent.generate_str(
        "Validate this SQL: SELECT * FROM FLIGHT_ANALYTICS.INFORMATION_SCHEMA.TABLES LIMIT 5"
    )
    
    # Verify validate_sql was called
    await session.assert_that(
        Expect.tools.was_called("validate_sql"),
        name="validate_sql_called"
    )
    
    # Verify response indicates SELECT * is not allowed
    await session.assert_that(
        Expect.content.regex(r"(?i)(SELECT \*|not allowed|explicit column|specify)"),
        response=response,
        name="select_star_rejected"
    )


@task("Test database connection check")
@with_agent("default")
async def test_db_connection(agent, session):
    """Verify that database connection can be tested."""
    response = await agent.generate_str(
        "Check if the Snowflake database is reachable"
    )
    
    # Verify validate_db_connection was called
    await session.assert_that(
        Expect.tools.was_called("validate_db_connection"),
        name="db_connection_called"
    )
    
    # Verify response indicates connection status
    await session.assert_that(
        Expect.content.regex(r"(?i)(up|running|reachable|connected|available)"),
        response=response,
        name="connection_status_returned"
    )
