"""Lineage workflow prompt for AI agents."""


def lineage_workflow_instructions() -> str:
    """
    Instructions for AI agents on how to use the lineage tools.
    
    This prompt should be read by AI agents before using lineage tools.
    """
    return """
## Lineage Server Tool Usage Instructions

When a user requests lineage information, follow this workflow:

### If the user explicitly requests a specific tool:
- Use that tool directly (e.g., "use generate_model_lineage for X")

### For general lineage requests:
1. First call `resolve_input` to validate the data_product, model_name, and column_name
2. If validation succeeds: Call the appropriate lineage tool
   - For column lineage: `generate_column_lineage`
   - For model lineage: `generate_model_lineage`
3. If validation fails: Report the error and show available options

### Available Tools:
- `ping`: Test server connectivity
- `resolve_input`: Validate inputs before lineage operations
- `generate_column_lineage`: Trace a column through upstream models
- `generate_model_lineage`: Trace model dependencies upstream

### Example Workflow:
User: "What is the lineage of the bookings model in flight_information?"

1. Call resolve_input(data_product="flight_information", model_name="bookings")
2. If success: Call generate_model_lineage(data_product="flight_information", model_name="bookings")
3. Present the lineage results to the user
"""
