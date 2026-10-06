"""
Data Retrieval Evaluation Tests

Tests for end-to-end data workflows including:
- Complete RCA (Root Cause Analysis) workflow
- Data query with model validation
- Multi-layer data inspection
"""

from mcp_eval import task, Expect, with_agent


@task("Test complete RCA workflow")
@with_agent("default")
async def test_rca_workflow(agent, session):
    """
    Verify the complete Root Cause Analysis workflow:
    1. Validate inputs with resolve_input
    2. Get column lineage
    3. Attempt data retrieval (may fail if tables not accessible)
    """
    response = await agent.generate_str(
        """I need to investigate the flight_distance_type column in flights 
        (flight_analytics). Show me the complete column lineage."""
    )
    
    # Verify resolve_input is called first for validation
    await session.assert_that(
        Expect.tools.was_called("resolve_input"),
        name="resolve_input_called"
    )
    
    # Verify lineage tool is called after validation
    await session.assert_that(
        Expect.tools.was_called("generate_column_lineage"),
        name="column_lineage_called"
    )
    
    # Verify response quality with LLM judge
    await session.assert_that(
        Expect.judge.llm(
            rubric="""The response should:
            1. Show complete column lineage from source to target
            2. Identify the source tables (stg_flights, stg_boarding_passes)
            3. Show the transformation path through intermediate models""",
            min_score=0.7
        ),
        response=response,
        name="response_quality"
    )
    
    # Performance check - should complete within 30 seconds
    await session.assert_that(
        Expect.performance.response_time_under(30000),
        name="performance_ok"
    )


@task("Test data query with model validation")
@with_agent("default")
async def test_data_query_with_validation(agent, session):
    """
    Verify that data queries include SQL validation before execution.
    Uses simple Snowflake functions accessible to any authenticated user.
    """
    response = await agent.generate_str(
        "Validate and execute this SQL: SELECT CURRENT_TIMESTAMP() AS current_time, CURRENT_USER() AS user_name, CURRENT_ROLE() AS role_name"
    )
    
    # Verify SQL validation and data retrieval
    await session.assert_that(
        Expect.tools.was_called("validate_sql"),
        name="sql_validated"
    )
    await session.assert_that(
        Expect.tools.was_called("get_data"),
        name="data_fetched"
    )
    
    # Verify response contains expected data
    await session.assert_that(
        Expect.content.regex(r"(?i)(current_time|timestamp|time)"),
        response=response,
        name="has_timestamp"
    )
    await session.assert_that(
        Expect.content.regex(r"(?i)(PUBLIC|user|role)"),
        response=response,
        name="has_role_info"
    )


@task("Test data retrieval returns actual rows")
@with_agent("default")
async def test_get_data_returns_rows(agent, session):
    """Verify that get_data returns actual data rows from the database."""
    response = await agent.generate_str(
        "Execute this query and show me the results: SELECT CURRENT_DATE() AS today, CURRENT_USER() AS username"
    )
    
    # Verify get_data was called
    await session.assert_that(
        Expect.tools.was_called("get_data"),
        name="get_data_called"
    )
    
    # Verify response contains date/user data
    await session.assert_that(
        Expect.content.regex(r"(?i)(today|date|username|user|2026)"),
        response=response,
        name="contains_query_results"
    )


@task("Test efficient workflow execution")
@with_agent("default")
async def test_efficient_workflow(agent, session):
    """
    Verify that the agent executes workflows efficiently without
    unnecessary tool calls or backtracking.
    """
    response = await agent.generate_str(
        "What is the lineage of flight_distance_type in flights (flight_analytics)?"
    )
    
    # Verify resolve_input was called
    await session.assert_that(
        Expect.tools.was_called("resolve_input"),
        name="resolve_input_called"
    )
    
    # Verify lineage was generated
    await session.assert_that(
        Expect.tools.was_called("generate_column_lineage"),
        name="lineage_generated"
    )
    
    # Verify efficient execution - should complete in max 3 LLM iterations
    await session.assert_that(
        Expect.performance.max_iterations(3),
        name="efficient_execution"
    )
