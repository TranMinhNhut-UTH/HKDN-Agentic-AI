import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from shared.models import Report


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS daily_jobs (
                    job_key TEXT PRIMARY KEY, owner TEXT NOT NULL, status TEXT NOT NULL,
                    lease_until REAL NOT NULL, report_id TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request TEXT NOT NULL, mode TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    steps TEXT NOT NULL DEFAULT '[]', report_id TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT NOT NULL, mode TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (id, mode)
                );
                CREATE TABLE IF NOT EXISTS report_articles (
                    report_id TEXT NOT NULL, article_id TEXT NOT NULL, mode TEXT NOT NULL,
                    PRIMARY KEY (report_id, article_id, mode)
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def claim_daily(self, key, owner, lease_seconds=3600):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM daily_jobs WHERE job_key=?", (key,)).fetchone()
            if row and (row["status"] == "done" or (row["status"] == "running" and row["lease_until"] > time.time())):
                return False
            db.execute("""INSERT INTO daily_jobs(job_key,owner,status,lease_until) VALUES(?,?,'running',?)
                       ON CONFLICT(job_key) DO UPDATE SET owner=excluded.owner,status='running',
                       lease_until=excluded.lease_until,error=NULL,report_id=NULL""", (key, owner, time.time() + lease_seconds))
        return True

    def finish_daily(self, key, owner, status, report_id=None, error=None):
        with self.connect() as db:
            cursor = db.execute("UPDATE daily_jobs SET status=?,report_id=?,error=?,lease_until=0 WHERE job_key=? AND owner=?",
                                (status, report_id, error, key, owner))
            if cursor.rowcount != 1:
                raise RuntimeError("Đã mất quyền sở hữu daily job")

    def save_report(self, report: Report):
        with self.connect() as db:
            db.execute("INSERT INTO reports VALUES(?,?)", (report.id, report.model_dump_json()))
            for article in report.articles:
                db.execute("INSERT OR REPLACE INTO articles VALUES(?,?,?)", (article.id, report.mode, article.model_dump_json()))
                db.execute("INSERT INTO report_articles VALUES(?,?,?)", (report.id, article.id, report.mode))

    def create_run(self, run_id, request, mode):
        with self.connect() as db:
            # One running web execution per local instance/DB, across processes.
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM runs WHERE status IN ('queued','running')").fetchone():
                raise RuntimeError("Một Agent đang chạy; vui lòng đợi hoàn tất")
            db.execute("INSERT INTO runs(id,request,mode,status,created_at) VALUES(?,?,?,'queued',?)",
                       (run_id, request, mode, utc_now()))

    def update_run(self, run_id, status=None, steps=None, report_id=None, error=None):
        fields, values = [], []
        for name, value in (("status", status), ("steps", None if steps is None else json.dumps(steps, ensure_ascii=False)),
                            ("report_id", report_id), ("error", error)):
            if value is not None:
                fields.append(name + "=?")
                values.append(value)
        if fields:
            with self.connect() as db:
                db.execute("UPDATE runs SET " + ",".join(fields) + " WHERE id=?", (*values, run_id))

    def recover_runs(self):
        # Called at app startup. This local app supports a single uvicorn worker.
        with self.connect() as db:
            db.execute("UPDATE runs SET status='failed',error='Server đã dừng trước khi hoàn thành; hãy chạy lại.' "
                       "WHERE status IN ('queued','running')")

    def get_run(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["steps"] = json.loads(result["steps"])
        return result

    def history(self, limit=50):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "steps": json.loads(row["steps"])} for row in rows]

    def get_report(self, report_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
        return Report.model_validate_json(row["payload"]) if row else None
