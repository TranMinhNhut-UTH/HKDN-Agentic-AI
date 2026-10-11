"""LIVE-path integration tests with Gemini and RSS entirely mocked."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from google import genai
from google.genai import errors, types
from shared.config import Settings
from shared.models import Plan, Analysis, Evaluation
from shared.rss import RSSReader
from shared.web import create_app

SECRET = "nv15-unit-test-credential"


def configure(monkeypatch, tmp_path, status=503, failures=1, budget=16):
    sdk = MagicMock()
    monkeypatch.setattr(genai, "Client", lambda **kwargs: sdk)
    sleeps = []
    monkeypatch.setattr("shared.llm.time.sleep", sleeps.append)
    article = RSSReader(Settings()).fetch("bbc")[0]
    monkeypatch.setattr(RSSReader, "fetch", lambda self, source: [article])
    remaining, collection_calls = failures, 0
    def generate(**kwargs):
        nonlocal remaining, collection_calls
        schema = kwargs["config"].response_schema
        if schema is Plan:
            value = Plan(topic="AI", count=1, tool="news_workflow", rationale="test")
        elif schema is Analysis:
            value = Analysis(findings=[{"article_id": article.id, "category": "test", "summary": article.excerpt,
                "evidence_quote": article.excerpt}], reason="test evidence")
        elif schema is Evaluation:
            value = Evaluation(revise=False, reason="test evaluation")
        else:
            if remaining:
                remaining -= 1
                cls = errors.ServerError if status >= 500 else errors.ClientError
                raise cls(status, {"error": {"code": status, "message": f"Temporary failure key={SECRET}"},
                                   "raw_private_response": SECRET})
            collection_calls += 1
            name, args = ("fetch_rss", {"source": "bbc"}) if collection_calls == 1 else (
                "finish_collection", {"article_ids": [article.id], "rationale": "test relevance"})
            call = types.FunctionCall(name=name, args=args)
            content = types.Content(role="model", parts=[types.Part(function_call=call)])
            return SimpleNamespace(function_calls=[call], candidates=[SimpleNamespace(content=content)])
        return SimpleNamespace(text=value.model_dump_json())
    sdk.models.generate_content.side_effect = generate
    settings = Settings(mode="live", api_key=SECRET, max_api_calls=budget,
                        data_dir=tmp_path / "data", report_dir=tmp_path / "reports")
    return create_app(settings), sdk, sleeps


def start(client):
    response = client.post("/api/runs", json={"request": "1 tin AI"})
    assert response.status_code == 202
    return client.get("/api/runs/" + response.json()["id"]).json()


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_nv15_transient_retry_success(monkeypatch, tmp_path, status):
    app, sdk, sleeps = configure(monkeypatch, tmp_path, status=status)
    with TestClient(app) as client:
        run = start(client)
        assert run["status"] == "completed" and run["mode"] == "live"
        report = client.get("/api/reports/" + run["report_id"]).json()
        assert report["api_calls"] == sdk.models.generate_content.call_count == 6
        assert report["mode"] == "live" and sleeps == [1]
        assert {s["agent"] for s in report["steps"]} >= {"Planner", "Collector", "Analyst", "Coordinator"}


def test_nv15_retry_exhaustion_safe_api_traceback_and_new_run(monkeypatch, tmp_path, caplog):
    app, sdk, sleeps = configure(monkeypatch, tmp_path, failures=3)
    with TestClient(app) as client:
        run = start(client)
        assert run["status"] == "failed" and run["report_id"] is None
        assert "HTTP=503" in run["error"] and "Temporary failure" in run["error"]
        assert SECRET not in str(run)
        assert "HTTP=503" in run["steps"][-1]["detail"]
        assert sdk.models.generate_content.call_count == 4 and sleeps == [1, 2]
        assert "NV15 failed" in caplog.text and "Traceback" in caplog.text
        assert SECRET not in caplog.text and "raw_private_response" not in caplog.text
        # Failure releases the active-run guard; subsequent request can succeed.
        assert start(client)["status"] == "completed"


def test_nv15_budget_limits_retries_before_first_report(monkeypatch, tmp_path):
    app, sdk, sleeps = configure(monkeypatch, tmp_path, failures=3, budget=2)
    with TestClient(app) as client:
        run = start(client)
        assert run["status"] == "failed" and "HTTP=503" in run["error"]
        assert sdk.models.generate_content.call_count == 2 and sleeps == []


def test_nv15_budget_retains_report_without_evaluation(monkeypatch, tmp_path):
    app, sdk, sleeps = configure(monkeypatch, tmp_path, failures=0, budget=4)
    with TestClient(app) as client:
        run = start(client)
        assert run["status"] == "incomplete" and run["report_id"]
        report = client.get("/api/reports/" + run["report_id"]).json()
        assert report["api_calls"] == sdk.models.generate_content.call_count == 4
        assert not report["complete"] and any(s["action"] == "budget_limit" for s in report["steps"])


def test_nv15_client_error_not_retried(monkeypatch, tmp_path):
    app, sdk, sleeps = configure(monkeypatch, tmp_path, status=403)
    with TestClient(app) as client:
        run = start(client)
        assert run["status"] == "failed" and "HTTP=403" in run["error"]
        assert sdk.models.generate_content.call_count == 2 and sleeps == []
