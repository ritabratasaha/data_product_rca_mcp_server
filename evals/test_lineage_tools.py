"""
Lineage Tools Evaluation Tests

Tests for core lineage functionality including:
- resolve_input validation
- Column lineage tracing
- Model lineage dependencies
"""

from mcp_eval import task, Expect, with_agent


@task("Test resolve_input validates data product and model")
@with_agent("default")
async def test_resolve_input(agent, session):
    """Verify that resolve_input correctly validates data product and model names."""
    response = await agent.generate_str(
        "Validate that the model 'flights' exists in 'flight_analytics' data product"
    )
    
    # Verify resolve_input was called
    await session.assert_that(
        Expect.tools.was_called("resolve_input"),
        name="resolve_input_called"
    )
    
    # Verify response contains the model name
    await session.assert_that(
        Expect.content.contains("flights"),
        response=response,
        name="contains_model_name"
    )


@task("Test column lineage traces through all layers")
@with_agent("default")
async def test_column_lineage(agent, session):
    """Verify that column lineage traces flight_distance_type through all upstream layers."""
    response = await agent.generate_str(
        "Get the column lineage for flight_distance_type in flights model, flight_analytics data product"
    )
    
    # Verify resolve_input is called first, then generate_column_lineage
    await session.assert_that(
        Expect.tools.sequence(["resolve_input", "generate_column_lineage"]),
        name="correct_tool_sequence"
    )
    
    # Verify the lineage includes the staging layer
    await session.assert_that(
        Expect.content.contains("stg_flights"),
        response=response,
        name="contains_stg_flights"
    )


@task("Test model lineage returns upstream dependencies")
@with_agent("default")
async def test_model_lineage(agent, session):
    """Verify that model lineage returns all upstream dependencies."""
    response = await agent.generate_str(
        "Get the model lineage for the 'flights' model in 'flight_analytics' data product. Show all upstream dependencies."
    )
    
    # Verify resolve_input is called first for validation
    await session.assert_that(
        Expect.tools.was_called("resolve_input"),
        name="resolve_input_called"
    )
    
    # Verify the correct tool sequence
    await session.assert_that(
        Expect.tools.sequence(["resolve_input", "generate_model_lineage"]),
        name="correct_tool_sequence"
    )
    
    # Verify response contains the intermediate model
    await session.assert_that(
        Expect.content.contains("int_flight_boarding"),
        response=response,
        name="contains_intermediate_model"
    )


@task("Test invalid model returns helpful error")
@with_agent("default")
async def test_invalid_model(agent, session):
    """Verify that an invalid model name returns available options."""
    response = await agent.generate_str(
        "Get the lineage for model 'nonexistent_model' in flight_analytics"
    )
    
    # Verify resolve_input was called
    await session.assert_that(
        Expect.tools.was_called("resolve_input"),
        name="resolve_input_called"
    )
    
    # Verify response indicates an error or lists available models
    await session.assert_that(
        Expect.content.regex(r"(?i)(not found|invalid|available|error)"),
        response=response,
        name="error_or_suggestions"
    )
