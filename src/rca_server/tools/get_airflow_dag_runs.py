"""
Airflow DAG run details tool using the Airflow 2.x REST API.

Given a DAG ID and date, returns:
  - How many times the DAG ran that day.
  - Status and duration of the last non-skipped run (success or failed).
  - 7-day rolling average duration.
  - Full task logs and dbt model list from the last non-skipped run.

Environment variables required:
  AIRFLOW_BASE_URL   – e.g. http://localhost:8080
  AIRFLOW_USERNAME   – basic-auth username
  AIRFLOW_PASSWORD   – basic-auth password
"""

import os
import re
from datetime import datetime, timedelta

import httpx
from langfuse import observe

from rca_server.logger import get_logger

logger = get_logger("get_airflow_dag_runs")

# Regex to extract dbt model names from CLI output.
# Example: "3 of 16 OK created sql table model staging.stg_routes ... [SUCCESS 1 in 1.91s]"
_DBT_MODEL_RE = re.compile(r"OK created \w+ \w+ model (\S+)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(dag_id: str, date: str, message: str, details: str) -> dict:
    """Standardised error response."""
    return {
        "success": False, "dag_id": dag_id, "date": date,
        "total_runs": 0, "last_run": None, "avg_duration_7d_seconds": None,
        "message": message, "error_details": details,
    }


async def _test_airflow_connection(
    base_url: str, auth: tuple[str, str]
) -> tuple[bool, str | None]:
    """Hit /api/v1/health to verify Airflow is reachable."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/api/v1/health", auth=auth, timeout=10
            )
            if resp.status_code == 200:
                return True, None
            return False, f"Airflow returned status {resp.status_code}"
    except Exception as e:
        return False, f"Cannot reach Airflow at {base_url}: {e}"


async def _fetch_task_log(
    client: httpx.AsyncClient, base_url: str, auth: tuple[str, str],
    dag_id: str, run_id: str, task_id: str, try_number: int,
) -> str:
    """Fetch the full log of a single task attempt. Returns '' on error."""
    try:
        resp = await client.get(
            f"{base_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}"
            f"/taskInstances/{task_id}/logs/{try_number}",
            auth=auth, timeout=15,
        )
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

@observe()
async def get_airflow_dag_runs(dag_id: str, date: str) -> dict:
    """
    Get Airflow DAG run details for a specific date.

    Returns total run count, the last non-skipped run with full logs,
    7-day average duration, and dbt model list extracted from the logs.

    Args:
        dag_id: The Airflow DAG identifier (e.g. "dbt_daily_run").
        date:   Target date in YYYY-MM-DD format.
    """
    # --- Config ---
    base_url = os.getenv("AIRFLOW_BASE_URL")
    username = os.getenv("AIRFLOW_USERNAME")
    password = os.getenv("AIRFLOW_PASSWORD")

    if not all([base_url, username, password]):
        return _error(dag_id, date, "Airflow configuration incomplete",
                      "Set AIRFLOW_BASE_URL, AIRFLOW_USERNAME, AIRFLOW_PASSWORD")

    auth = (username, password)

    reachable, conn_error = await _test_airflow_connection(base_url, auth)
    if not reachable:
        return _error(dag_id, date, "Airflow is not reachable", conn_error)

    try:
        target = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return _error(dag_id, date, "Invalid date format", "Use YYYY-MM-DD")

    date_start = target.strftime("%Y-%m-%dT00:00:00+00:00")
    date_end = (target + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+00:00")
    seven_days_ago = (target - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00+00:00")

    try:
        async with httpx.AsyncClient() as client:
            # --- All DAG runs for the target date (for total count) ---
            resp = await client.get(
                f"{base_url}/api/v1/dags/{dag_id}/dagRuns",
                params={"execution_date_gte": date_start,
                        "execution_date_lte": date_end},
                auth=auth, timeout=15,
            )
            resp.raise_for_status()
            day_runs = resp.json().get("dag_runs", [])
            total_runs = len(day_runs)

            # --- 7-day average duration ---
            resp = await client.get(
                f"{base_url}/api/v1/dags/{dag_id}/dagRuns",
                params={"execution_date_gte": seven_days_ago,
                        "execution_date_lte": date_end},
                auth=auth, timeout=15,
            )
            resp.raise_for_status()
            week_durations = [
                r["duration"] for r in resp.json().get("dag_runs", [])
                if r.get("duration") is not None
            ]
            avg_duration = (
                round(sum(week_durations) / len(week_durations), 1)
                if week_durations else None
            )

            # --- Find the last non-skipped run (walk backwards) ---
            last_run = None
            for run in reversed(day_runs):
                run_id = run.get("dag_run_id", "")

                resp = await client.get(
                    f"{base_url}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances",
                    auth=auth, timeout=15,
                )
                resp.raise_for_status()
                task_list = resp.json().get("task_instances", [])

                # A run is "not skipped" if any task state != "skipped"
                has_real_work = any(
                    t.get("state") != "skipped" for t in task_list
                )
                if not has_real_work:
                    continue

                # This is the run we want — fetch logs for each task
                tasks = []
                for task in task_list:
                    task_id = task.get("task_id", "")
                    log_excerpt = await _fetch_task_log(
                        client, base_url, auth, dag_id, run_id,
                        task_id, task.get("try_number", 1),
                    )
                    tasks.append({
                        "task_id": task_id,
                        "state": task.get("state", "unknown"),
                        "duration_seconds": task.get("duration"),
                        "log_excerpt": log_excerpt,
                    })

                # Extract dbt models from run_dbt task log
                dbt_models = []
                for t in tasks:
                    if t["task_id"] == "run_dbt" and t["log_excerpt"]:
                        dbt_models = list(dict.fromkeys(
                            _DBT_MODEL_RE.findall(t["log_excerpt"])
                        ))

                last_run = {
                    "run_id": run_id,
                    "state": run.get("state", "unknown"),
                    "duration_seconds": run.get("duration"),
                    "dbt_models": dbt_models,
                    "tasks": tasks,
                }
                break

            # --- Build message ---
            if last_run:
                state = last_run["state"]
                dur = last_run["duration_seconds"]
                dur_str = f" ({dur}s)" if dur else ""
                message = (
                    f"DAG '{dag_id}' ran {total_runs} time(s) on {date}. "
                    f"Last non-skipped run: {state}{dur_str}."
                )
            else:
                message = (
                    f"DAG '{dag_id}' ran {total_runs} time(s) on {date}. "
                    f"All runs were skipped."
                )

            if avg_duration is not None:
                message += f" Avg duration (7d): {avg_duration}s."

            logger.info(message)
            return {
                "success": True,
                "dag_id": dag_id,
                "date": date,
                "total_runs": total_runs,
                "last_run": last_run,
                "avg_duration_7d_seconds": avg_duration,
                "message": message,
                "error_details": None,
            }

    except Exception as e:
        logger.error(f"Error fetching Airflow data: {e}")
        return _error(dag_id, date, "Failed to fetch DAG run details", str(e))
