from fastapi.testclient import TestClient
from shared.config import Settings
from shared.llm import MockProvider
from shared.models import Evaluation
from shared.web import create_app


def app_for(tmp_path, provider_factory=None):
    return create_app(Settings(data_dir=tmp_path / "data", report_dir=tmp_path / "reports"), provider_factory)


def test_end_to_end_history_download_and_persistence(tmp_path):
    app = app_for(tmp_path)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/api/config").json()["mode"] == "mock"
        response = client.post("/api/runs", json={"request": "Tổng hợp 5 tin về AI"})
        assert response.status_code == 202
        run = client.get("/api/runs/" + response.json()["id"]).json()
        assert run["status"] == "completed"
        assert any(s["agent"] == "Planner" and s["action"] == "evaluate" for s in run["steps"])
        report = client.get("/api/reports/" + run["report_id"]).json()
        assert len(report["analysis"]["findings"]) == 5
        assert report["api_calls"] == 7
        for fmt in ("json", "md"):
            result = client.get(f'/api/reports/{run["report_id"]}/download?format={fmt}')
            assert result.status_code == 200 and "attachment" in result.headers["content-disposition"]
        assert len(client.get("/api/runs").json()) == 1
    with TestClient(app_for(tmp_path)) as client:
        assert client.get("/api/runs").json()[0]["status"] == "completed"


def test_validation_missing_and_busy(tmp_path):
    app = app_for(tmp_path)
    with TestClient(app) as client:
        for request in ("", "   ", "x" * 1001):
            assert client.post("/api/runs", json={"request": request}).status_code == 422
        assert client.get("/api/runs/missing").status_code == 404
        assert client.get("/api/reports/missing").status_code == 404
        assert client.get("/api/reports/x/download?format=html").status_code == 422
        app.state.store.create_run("busy", "AI", "mock")
        assert client.post("/api/runs", json={"request": "AI"}).status_code == 409


def test_error_and_recovery(tmp_path):
    class BrokenPlanner(MockProvider):
        def plan(self, request):
            raise TimeoutError()
    app = app_for(tmp_path, BrokenPlanner)
    with TestClient(app) as client:
        result = client.post("/api/runs", json={"request": "AI"}).json()
        run = client.get("/api/runs/" + result["id"]).json()
        assert run["status"] == "failed" and "TimeoutError" in run["error"]
        app.state.store.create_run("crashed", "AI", "mock")
    with TestClient(app_for(tmp_path)) as client:
        assert client.get("/api/runs/crashed").json()["status"] == "failed"


def test_planner_revises_at_most_once(tmp_path):
    class RevisingPlanner(MockProvider):
        def evaluate(self, request, report):
            self.budget.consume()
            return Evaluation(revise=True, topic="AI", reason="test revise")
    with TestClient(app_for(tmp_path, RevisingPlanner)) as client:
        result = client.post("/api/runs", json={"request": "AI"}).json()
        run = client.get("/api/runs/" + result["id"]).json()
        assert run["status"] == "incomplete"
        assert sum(s["action"] == "revise" for s in run["steps"]) == 1
        assert sum(s["action"] == "evaluate" for s in run["steps"]) == 2


def test_budget_retains_existing_report(tmp_path):
    settings = Settings(max_api_calls=6, data_dir=tmp_path / "data", report_dir=tmp_path / "reports")
    with TestClient(create_app(settings)) as client:
        result = client.post("/api/runs", json={"request": "5 tin AI"}).json()
        run = client.get("/api/runs/" + result["id"]).json()
        assert run["status"] == "incomplete" and run["report_id"]
        report = client.get("/api/reports/" + run["report_id"]).json()
        assert report["api_calls"] == 6 and not report["complete"]
