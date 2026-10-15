import pytest
from shared.agents import NewsWorkflow, AnalystAgent, Trace
from shared.config import Settings
from shared.llm import MockProvider, BudgetExceeded
from shared.models import Analysis
from shared.rss import RSSReader


def test_agents_coordinate_and_try_other_sources():
    report = NewsWorkflow(Settings()).run("AI", 5)
    assert report.complete and len(report.analysis.findings) == 5
    assert len([s for s in report.steps if s["action"] == "fetch_rss"]) == 3
    assert report.mode == "mock" and report.api_calls == 5


def test_missing_data_feedback_bounded():
    report = NewsWorkflow(Settings()).run("nonexistentxyz", 5)
    assert not report.complete and report.analysis.findings == []
    assert len([s for s in report.steps if s["action"] == "round"]) == 2
    assert any(s["action"] == "request_more" for s in report.steps)


def test_budget_and_step_limit():
    with pytest.raises(BudgetExceeded):
        NewsWorkflow(Settings(max_api_calls=1)).run("AI")
    with pytest.raises(RuntimeError, match="Collector"):
        NewsWorkflow(Settings(max_steps=1)).run("AI")


def test_grounding_rejects_unknown_id_and_fake_quote():
    settings = Settings()
    class BadAnalyst(MockProvider):
        def analyze(self, *args):
            return Analysis(findings=[{"article_id": "fake", "category": "x", "summary": "x", "evidence_quote": "x"}], reason="bad")
    analysis = AnalystAgent(BadAnalyst(settings), Trace()).run("AI", 1, RSSReader(settings).fetch("bbc"))
    assert analysis.needs_more and analysis.findings == []


def test_source_failure_tries_next():
    class BrokenReader(RSSReader):
        def fetch(self, source):
            if source == "bbc":
                raise TimeoutError()
            return super().fetch(source)
    report = NewsWorkflow(Settings(), reader=BrokenReader(Settings())).run("AI", 3)
    assert report.complete
    assert any(s["action"] == "source_error" for s in report.steps)
