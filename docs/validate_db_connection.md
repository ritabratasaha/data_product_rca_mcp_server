# validate_db_connection

## Purpose

Checks that Snowflake is reachable. Runs `SELECT CURRENT_TIMESTAMP()` and retries once after 5 seconds if the first attempt fails.

## Diagram

```mermaid
flowchart TD
  start[Agent calls validate_db_connection] --> env{SNOWFLAKE_ACCOUNT set?}
  env -->|no| failEnv[Return not configured]
  env -->|yes| try1[Query CURRENT_TIMESTAMP]
  try1 -->|ok| success[Return server_time]
  try1 -->|fail| wait[Wait 5 seconds]
  wait --> try2[Retry query]
  try2 -->|ok| success
  try2 -->|fail| fail[Return error after 2 attempts]
```

## Inputs

None.

## Outputs

| Field | Meaning |
|---|---|
| `success` | Whether Snowflake answered |
| `message` | Short result text |
| `server_time` | Database clock if connected, else `null` |
| `error_details` | Failure reason, or `null` |

## Source

[`src/rca_server/tools/validate_db_connection.py`](../src/rca_server/tools/validate_db_connection.py)
