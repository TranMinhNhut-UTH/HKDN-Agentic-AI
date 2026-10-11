"""Offline only: Gemini Client and RSS are replaced before any request."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from google import genai
from google.genai import errors, types
from shared.config import Settings
from shared.llm import GeminiProvider, BudgetExceeded
from shared.models import Plan
from shared.diagnostics import exception_summary, log_exception
from shared.automation import weekly_job
from shared.agents import NewsWorkflow
from shared.rss import RSSReader
from shared.storage import Store

SECRET = "unit-test-secret-never-log"


def api_error(code, message="Service temporarily unavailable"):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": message, "status": "UNAVAILABLE"},
                      "private_response": SECRET})


def setup_provider(monkeypatch, limit=16, attempts=3):
    client = MagicMock()
    sleeps = []
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)
    monkeypatch.setattr("shared.llm.time.sleep", sleeps.append)
    provider = GeminiProvider(Settings(mode="live", api_key=SECRET, max_api_calls=limit), retry_attempts=attempts)
    return provider, client, sleeps


def plan_response():
    return SimpleNamespace(text=Plan(topic="AI", count=5, tool="news_workflow", rationale="test").model_dump_json())


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_transient_error_retries_then_succeeds(monkeypatch, status):
    provider, client, sleeps = setup_provider(monkeypatch)
    client.models.generate_content.side_effect = [api_error(status), plan_response()]
    assert provider.plan("AI").topic == "AI"
    assert provider.budget.calls == client.models.generate_content.call_count == 2
    assert sleeps == [1]


def test_three_attempt_cap_backoff_and_redacted_retry_log(monkeypatch, caplog):
    provider, client, sleeps = setup_provider(monkeypatch)
    client.models.generate_content.side_effect = api_error(503, f"Overloaded api_key={SECRET}")
    with pytest.raises(errors.ServerError):
        provider.plan("AI")
    assert provider.budget.calls == client.models.generate_content.call_count == 3
    assert sleeps == [1, 2]
    assert SECRET not in caplog.text and "HTTP=503" in caplog.text
    assert "private_response" not in caplog.text


def test_budget_stops_retry_without_masking_last_http_error(monkeypatch):
    provider, client, sleeps = setup_provider(monkeypatch, limit=2)
    client.models.generate_content.side_effect = api_error(502)
    with pytest.raises(errors.ServerError) as caught:
        provider.plan("AI")
    assert caught.value.code == 502
    assert provider.budget.calls == client.models.generate_content.call_count == 2
    assert sleeps == [1]
    with pytest.raises(BudgetExceeded):
        provider.plan("AI")
    assert client.models.generate_content.call_count == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 501])
def test_non_transient_status_not_retried(monkeypatch, status):
    provider, client, sleeps = setup_provider(monkeypatch)
    client.models.generate_content.side_effect = api_error(status)
    with pytest.raises(errors.APIError):
        provider.plan("AI")
    assert provider.budget.calls == client.models.generate_content.call_count == 1
    assert not sleeps


def test_base_provider_default_remains_single_attempt(monkeypatch):
    provider, client, sleeps = setup_provider(monkeypatch, attempts=1)
    client.models.generate_content.side_effect = api_error(503)
    with pytest.raises(errors.ServerError):
        provider.plan("AI")
    assert client.models.generate_content.call_count == 1 and not sleeps


def test_collector_retry_does_not_duplicate_history(monkeypatch):
    provider, client, sleeps = setup_provider(monkeypatch)
    call = types.FunctionCall(name="fetch_rss", args={"source": "techcrunch"})
    content = types.Content(role="model", parts=[types.Part(function_call=call)])
    response = SimpleNamespace(function_calls=[call], candidates=[SimpleNamespace(content=content)])
    client.models.generate_content.side_effect = [api_error(504), response]
    history = []
    assert provider.collect({"topic": "AI", "count": 5, "attempted": [], "articles": []}, history)[0] == "fetch_rss"
    assert len(history) == 1 and provider.budget.calls == 2


def test_safe_traceback_redacts_chain_and_does_not_dump_response(caplog):
    import logging
    try:
        try:
            raise ValueError(f"authorization=Bearer {SECRET} key={SECRET}")
        except ValueError as cause:
            raise api_error(503, f"Service overloaded X-Goog-Api-Key: {SECRET}") from cause
    except errors.ServerError as exc:
        log_exception(logging.getLogger("test.safe"), "Weekly job failed", exc, (SECRET,))
    assert "Traceback (most recent call last)" in caplog.text
    assert "test_safe_traceback" in caplog.text and "HTTP=503" in caplog.text
    assert "Service overloaded" in caplog.text
    assert SECRET not in caplog.text and "private_response" not in caplog.text


def test_google_key_and_unknown_header_tokens_redacted():
    key = "AIza" + "X" * 35
    summary = exception_summary(ValueError(f"key={key} Authorization: Bearer unknown-credential token=another-credential"))
    assert key not in summary and "unknown-credential" not in summary and "another-credential" not in summary


def test_api_error_without_message_does_not_log_raw_body():
    error = api_error(503)
    error.message = None
    assert "private_response" not in exception_summary(error)
    assert SECRET not in exception_summary(error)


def test_nv14_failure_after_rss_releases_lease_and_retry_is_safe(monkeypatch, tmp_path, caplog):
    settings = Settings(mode="live", api_key=SECRET, data_dir=tmp_path / "data", report_dir=tmp_path / "reports")
    client = MagicMock()
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)
    sleeps = []
    monkeypatch.setattr("shared.llm.time.sleep", sleeps.append)
    original_fetch = RSSReader.fetch
    fetched = RSSReader(Settings()).fetch("techcrunch")
    monkeypatch.setattr(RSSReader, "fetch", lambda self, source: fetched)
    call = types.FunctionCall(name="fetch_rss", args={"source": "techcrunch"})
    content = types.Content(role="model", parts=[types.Part(function_call=call)])
    response = SimpleNamespace(function_calls=[call], candidates=[SimpleNamespace(content=content)])
    client.models.generate_content.side_effect = [response, api_error(503, f"Overloaded key={SECRET}"), api_error(503), api_error(503)]
    with pytest.raises(errors.ServerError):
        weekly_job(settings, day=date(2026, 10, 11))
    assert client.models.generate_content.call_count == 4 and sleeps == [1, 2]
    assert "Collector fetch_rss techcrunch" in caplog.text
    assert "Weekly job failed" in caplog.text and "HTTP=503" in caplog.text and "Traceback" in caplog.text
    assert SECRET not in caplog.text
    store = Store(settings.data_dir / "news.sqlite3")
    with store.connect() as db:
        row = db.execute("SELECT * FROM daily_jobs").fetchone()
        assert row["status"] == "failed" and row["lease_until"] == 0
        assert "HTTP=503" in row["error"] and SECRET not in row["error"]
        assert db.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0
    # Repeat the same LIVE job with a fully stubbed successful workflow. The
    # production code never switches to mock; this factory is a test double only.
    monkeypatch.setattr(RSSReader, "fetch", original_fetch)
    class SuccessfulTestWorkflow:
        def __init__(self, settings):
            self.inner = NewsWorkflow(Settings())
            self.provider = self.inner.provider
        def run(self, topic, count):
            report = self.inner.run(topic, count)
            report.mode = "live"
            return report
    result = weekly_job(settings, day=date(2026, 10, 11), workflow_factory=SuccessfulTestWorkflow)
    assert result["status"] == "done"
    assert weekly_job(settings, day=date(2026, 10, 11))["status"] == "skipped"
    assert client.models.generate_content.call_count == 4


def test_cli_returns_one_with_safe_status_and_traceback(monkeypatch, tmp_path, capsys, caplog):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "NV14-Automation/weekly_job.py"
    spec = importlib.util.spec_from_file_location("nv14_error_cli", path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    settings = Settings(mode="live", api_key=SECRET, data_dir=tmp_path / "data", report_dir=tmp_path / "reports")
    monkeypatch.setattr(cli.Settings, "load", lambda mode: settings)
    def failing_job(*args):
        raise api_error(500, f"Internal failure api_key={SECRET}")
    monkeypatch.setattr(cli, "weekly_job", failing_job)
    assert cli.main([]) == 1
    stderr = capsys.readouterr().err
    assert "HTTP=500" in stderr and SECRET not in stderr
    assert "Traceback" in caplog.text and SECRET not in caplog.text


def test_cleanup_failure_does_not_mask_saved_job(tmp_path, caplog):
    settings = Settings(data_dir=tmp_path / "data", report_dir=tmp_path / "reports")
    class CleanupFailureWorkflow:
        def __init__(self, settings):
            self.inner = NewsWorkflow(settings)
            self.provider = MagicMock()
            self.provider.close.side_effect = RuntimeError("cleanup failed")
        def run(self, topic, count):
            return self.inner.run(topic, count)
    result = weekly_job(settings, workflow_factory=CleanupFailureWorkflow)
    assert result["status"] == "done"
    assert "cleanup failed" in caplog.text
    assert weekly_job(settings)["status"] == "skipped"
