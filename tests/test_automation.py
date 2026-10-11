from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import pytest
from shared.automation import weekly_job, daily_job, iso_week
from shared import automation
from shared.config import Settings
from shared.storage import Store


def config(tmp_path):
    return Settings(data_dir=tmp_path / "data", report_dir=tmp_path / "reports")


def test_weekly_report_and_idempotency(tmp_path):
    settings = config(tmp_path)
    result = weekly_job(settings, day=date(2026, 1, 2))
    assert result["status"] == "done"
    assert result["key"].startswith("2026-W01:mock:")
    assert weekly_job(settings, day=date(2026, 1, 2))["status"] == "skipped"
    assert weekly_job(settings, day=date(2026, 1, 4))["status"] == "skipped"
    assert weekly_job(settings, day=date(2026, 1, 5))["status"] == "done"
    assert Path(result["paths"][0]).parent.parent.parent.name == "2026-W01"
    assert Store(settings.data_dir / "news.sqlite3").get_report(result["report_id"]).complete


def test_atomic_claim_and_expired_lease(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda owner: store.claim_daily("today", owner), ["a", "b", "c", "d"]))
    assert sum(results) == 1
    assert store.claim_daily("old", "a", lease_seconds=-1)
    assert store.claim_daily("old", "b")
    with pytest.raises(RuntimeError):
        store.finish_daily("old", "a", "done")


def test_failure_releases_for_retry(tmp_path):
    settings = config(tmp_path)
    class BrokenWorkflow:
        def __init__(self, settings):
            raise TimeoutError("test")
    with pytest.raises(TimeoutError):
        weekly_job(settings, workflow_factory=BrokenWorkflow)
    assert weekly_job(settings)["status"] == "done"


@pytest.mark.parametrize("day, expected", [
    (date(2020, 12, 31), "2020-W53"),
    (date(2021, 1, 1), "2020-W53"),
    (date(2021, 1, 3), "2020-W53"),
    (date(2021, 1, 4), "2021-W01"),
    (date(2025, 12, 29), "2026-W01"),
    (date(2026, 1, 4), "2026-W01"),
    (date(2026, 1, 5), "2026-W02"),
])
def test_iso_week_year_boundaries(day, expected):
    assert iso_week(day) == expected


def test_same_week_across_calendar_years(tmp_path):
    settings = config(tmp_path)
    result = weekly_job(settings, day=date(2020, 12, 31))
    assert result["status"] == "done"
    assert weekly_job(settings, day=date(2021, 1, 3))["status"] == "skipped"
    assert weekly_job(settings, day=date(2021, 1, 4))["status"] == "done"


def test_default_week_uses_vietnam_timezone(monkeypatch, tmp_path):
    class FrozenClock:
        @classmethod
        def now(cls, zone):
            # Sunday UTC, already Monday in Vietnam -> next ISO week.
            return datetime(2026, 1, 4, 18, 0, tzinfo=timezone.utc).astimezone(zone)
    monkeypatch.setattr(automation, "datetime", FrozenClock)
    result = weekly_job(config(tmp_path))
    assert result["key"].startswith("2026-W02:")


def test_topic_and_mode_separation(tmp_path):
    settings = config(tmp_path)
    day = date(2026, 1, 5)
    assert weekly_job(settings, day=day)["status"] == "done"
    assert weekly_job(settings, topic=" ai ", day=day)["status"] == "skipped"
    assert weekly_job(settings, topic="AI agents", day=day)["status"] == "done"
    # Stub workflow to validate key separation without contacting Gemini.
    class StubWorkflow:
        def __init__(self, settings):
            from shared.agents import NewsWorkflow
            self.inner = NewsWorkflow(config(tmp_path))
            self.provider = self.inner.provider
        def run(self, topic, count):
            report = self.inner.run(topic, count)
            report.mode = "live"
            return report
    live = Settings(mode="live", api_key="test-placeholder", data_dir=settings.data_dir, report_dir=settings.report_dir)
    assert weekly_job(live, day=day, workflow_factory=StubWorkflow)["status"] == "done"
    assert weekly_job(live, day=day, workflow_factory=StubWorkflow)["status"] == "skipped"


def test_incomplete_retries_same_week(tmp_path):
    settings = config(tmp_path)
    day = date(2026, 1, 5)
    first = weekly_job(settings, topic="nonexistentxyz", day=day)
    second = weekly_job(settings, topic="nonexistentxyz", day=day)
    assert first["status"] == second["status"] == "incomplete"
    assert first["report_id"] != second["report_id"]


def test_concurrent_weekly_job_executes_workflow_once(tmp_path):
    settings = config(tmp_path)
    # Initialize database before concurrent access, just as app setup would.
    Store(settings.data_dir / "news.sqlite3")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: weekly_job(settings, day=date(2026, 1, 5)), range(4)))
    assert [r["status"] for r in results].count("done") == 1
    assert [r["status"] for r in results].count("skipped") == 3
    assert len(list(settings.report_dir.rglob("*.json"))) == 1


def test_old_daily_records_do_not_collide(tmp_path):
    settings = config(tmp_path)
    store = Store(settings.data_dir / "news.sqlite3")
    store.claim_daily("2026-01-05:mock:32e83e92d45d", "legacy")
    store.finish_daily("2026-01-05:mock:32e83e92d45d", "legacy", "done")
    assert weekly_job(settings, day=date(2026, 1, 5))["status"] == "done"
    assert daily_job is weekly_job


@pytest.mark.parametrize("args, expected_mode", [([], "live"), (["--mode", "mock"], "mock")])
def test_cli_mode_default_is_scoped_to_nv14(monkeypatch, tmp_path, args, expected_mode):
    path = Path(__file__).resolve().parents[1] / "NV14-Automation/weekly_job.py"
    spec = importlib.util.spec_from_file_location("nv14_weekly_cli", path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    modes, topics = [], []
    def load(mode):
        modes.append(mode)
        return config(tmp_path)
    monkeypatch.setenv("APP_MODE", "mock")
    monkeypatch.setattr(cli.Settings, "load", load)
    monkeypatch.setattr(cli, "weekly_job", lambda settings, topic: topics.append(topic) or {"status": "skipped"})
    assert cli.main(args) == 0
    assert modes == [expected_mode] and topics == ["AI"]


def test_scheduler_script_weekly_monday_live_with_mocked_cmdlets():
    powershell = shutil.which("powershell")
    if not powershell:
        pytest.skip("Windows PowerShell required for script contract test")
    path = Path(__file__).resolve().parents[1] / "NV14-Automation/register_task.ps1"
    quoted = str(path).replace("'", "''")
    # Every scheduler cmdlet is a local stub: no scheduler registration/query.
    command = r'''
    $ErrorActionPreference = 'Stop'
    function Get-ScheduledTask { [CmdletBinding()] param($TaskName) return $null }
    function New-ScheduledTaskAction { param($Execute,$Argument,$WorkingDirectory)
        $script:CapturedAction = @{Execute=$Execute; Argument=$Argument; WorkingDirectory=$WorkingDirectory}; return 'action' }
    function New-ScheduledTaskTrigger { param([switch]$Weekly,$WeeksInterval,$DaysOfWeek,$At)
        $script:CapturedTrigger = @{Weekly=[bool]$Weekly; WeeksInterval=$WeeksInterval; DaysOfWeek=$DaysOfWeek; At=$At}; return 'trigger' }
    function New-ScheduledTaskSettingsSet { param([switch]$StartWhenAvailable,$MultipleInstances,$ExecutionTimeLimit) return 'settings' }
    function New-ScheduledTaskPrincipal { param($UserId,$LogonType,$RunLevel) return 'principal' }
    function Register-ScheduledTask { throw 'Registration must never be called in this test' }
    $source = (Get-Content -LiteralPath '__SCRIPT__' -Raw).Replace('$PSScriptRoot', "'__ROOT__'")
    & ([scriptblock]::Create($source)) -WhatIf | Out-Null
    @{Action=$script:CapturedAction; Trigger=$script:CapturedTrigger} | ConvertTo-Json -Compress
    '''.replace("__SCRIPT__", quoted).replace("__ROOT__", str(path.parent).replace("'", "''"))
    result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    payload = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
    assert payload["Trigger"] == {"Weekly": True, "WeeksInterval": 1, "DaysOfWeek": "Monday", "At": "08:00"}
    assert "weekly_job.py" in payload["Action"]["Argument"]
    assert "--mode live" in payload["Action"]["Argument"]
