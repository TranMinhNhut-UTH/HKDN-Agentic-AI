from contextlib import asynccontextmanager
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from shared.agents import markdown
from shared.config import ROOT, Settings
from shared.service import execute_request
from shared.storage import Store

FRONTEND = ROOT / "NV15-Agentic-AI/frontend"


class RunRequest(BaseModel):
    request: str = Field(min_length=1, max_length=1000)

    @field_validator("request")
    @classmethod
    def valid_request(cls, value):
        if not value.strip():
            raise ValueError("Yêu cầu không được để trống")
        return value.strip()


def create_app(settings=None, provider_factory=None):
    settings = settings or Settings.load()
    store = Store(settings.data_dir / "news.sqlite3")

    @asynccontextmanager
    async def lifespan(app):
        store.recover_runs()
        yield

    app = FastAPI(title="AI News Intelligence System", version="1.0.0", lifespan=lifespan)
    app.state.store = store
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/api/config")
    def config():
        return {"mode": settings.mode, "model": settings.model if settings.mode == "live" else "deterministic-mock",
                "max_api_calls": settings.max_api_calls, "max_steps": settings.max_steps,
                "max_rounds": settings.max_rounds, "max_plans": 2}

    @app.post("/api/runs", status_code=202)
    def start(payload: RunRequest, background: BackgroundTasks):
        run_id = uuid.uuid4().hex
        try:
            store.create_run(run_id, payload.request, settings.mode)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        kwargs = {"provider_factory": provider_factory} if provider_factory else {}
        background.add_task(execute_request, settings, store, run_id, payload.request, **kwargs)
        return {"id": run_id, "status": "queued", "mode": settings.mode}

    @app.get("/api/runs")
    def history():
        return store.history()

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str):
        result = store.get_run(run_id)
        if not result:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy")
        return result

    @app.get("/api/reports/{report_id}")
    def report_detail(report_id: str):
        report = store.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
        return report

    @app.get("/api/reports/{report_id}/download")
    def download(report_id: str, format: str = "md"):
        if format not in {"md", "json"}:
            raise HTTPException(status_code=422, detail="format phải là md hoặc json")
        report = store.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
        text = markdown(report) if format == "md" else report.model_dump_json(indent=2)
        return Response(text, media_type="text/markdown" if format == "md" else "application/json",
                        headers={"Content-Disposition": f'attachment; filename="report-{report.id}.{format}"'})

    return app
