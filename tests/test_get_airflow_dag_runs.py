"""Tests for the get_airflow_dag_runs tool."""

import os
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from rca_server.tools.get_airflow_dag_runs import get_airflow_dag_runs


class TestGetAirflowDagRuns:

    @pytest.mark.asyncio
    async def test_missing_airflow_config(self):
        """Error when Airflow env vars are not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AIRFLOW_BASE_URL", None)
            os.environ.pop("AIRFLOW_USERNAME", None)
            os.environ.pop("AIRFLOW_PASSWORD", None)

            result = await get_airflow_dag_runs("my_dag", "2026-09-20")

            assert result["success"] is False
            assert "AIRFLOW_BASE_URL" in result["error_details"]
            assert result["last_run"] is None

    @pytest.mark.asyncio
    async def test_airflow_unreachable(self):
        """Error when Airflow is not reachable."""
        env = {
            "AIRFLOW_BASE_URL": "http://localhost:8080",
            "AIRFLOW_USERNAME": "admin",
            "AIRFLOW_PASSWORD": "admin",
        }
        with patch.dict(os.environ, env):
            with patch(
                "rca_server.tools.get_airflow_dag_runs._test_airflow_connection",
                return_value=(False, "Cannot reach Airflow"),
            ):
                result = await get_airflow_dag_runs("my_dag", "2026-09-20")

                assert result["success"] is False
                assert "not reachable" in result["message"]
                assert result["last_run"] is None

    @pytest.mark.asyncio
    async def test_successful_dag_run(self):
        """Successful fetch returns flat response with last_run."""
        env = {
            "AIRFLOW_BASE_URL": "http://localhost:8080",
            "AIRFLOW_USERNAME": "admin",
            "AIRFLOW_PASSWORD": "admin",
        }

        dag_runs_response = {
            "dag_runs": [
                {"dag_run_id": "run_1", "state": "success", "duration": 150.0}
            ]
        }

        task_instances_response = {
            "task_instances": [
                {"task_id": "run_dbt", "state": "success",
                 "duration": 55.0, "try_number": 1}
            ]
        }

        mock_responses = [
            ("/logs/1", MagicMock(status_code=200, text="INFO - Task done")),
            ("/taskInstances", MagicMock(
                status_code=200,
                json=MagicMock(return_value=task_instances_response),
                raise_for_status=MagicMock(),
            )),
            ("/dagRuns", MagicMock(
                status_code=200,
                json=MagicMock(return_value=dag_runs_response),
                raise_for_status=MagicMock(),
            )),
            ("/health", MagicMock(status_code=200)),
        ]

        async def mock_get(url, **kwargs):
            for path, resp in mock_responses:
                if path in url:
                    return resp
            return MagicMock(status_code=404)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.dict(os.environ, env):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await get_airflow_dag_runs("my_dag", "2026-09-20")

                assert result["success"] is True
                assert result["total_runs"] == 1
                assert result["last_run"] is not None
                assert result["last_run"]["state"] == "success"
                assert result["last_run"]["duration_seconds"] == 150.0
                assert result["last_run"]["tasks"][0]["task_id"] == "run_dbt"
