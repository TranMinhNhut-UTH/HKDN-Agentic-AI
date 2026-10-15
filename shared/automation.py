import hashlib
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
from shared.agents import NewsWorkflow, save_report
from shared.config import setup_logging
from shared.storage import Store
from shared.llm import make_provider
from shared.diagnostics import log_exception, exception_summary


def iso_week(day: date):
    """ISO week-year, which may differ from the calendar year near New Year."""
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def weekly_job(settings, topic="AI", day=None, workflow_factory=NewsWorkflow):
    day = day or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    period = iso_week(day)
    digest = hashlib.sha256(topic.strip().casefold().encode()).hexdigest()[:12]
    key = f"{period}:{settings.mode}:{digest}"
    owner = uuid.uuid4().hex
    store = Store(settings.data_dir / "news.sqlite3")
    # Lease covers bounded API calls and RSS requests plus disk work.
    lease = max(3600, (settings.max_api_calls + settings.max_steps * settings.max_rounds) * settings.timeout * 2 + 300)
    # The legacy SQLite table/method names are retained to preserve existing data
    # and avoid changes to the shared Store used by NV15. Keys are now ISO weeks.
    if not store.claim_daily(key, owner, lease):
        setup_logging().info("Weekly job đã chạy/đang chạy: %s", key)
        return {"status": "skipped", "key": key}
    workflow, provider = None, None
    try:
        if workflow_factory is NewsWorkflow:
            # Retry policy is scoped to NV14, not the NV13/NV15 defaults.
            provider = make_provider(settings, retry_attempts=3)
            workflow = workflow_factory(settings, provider=provider)
        else:
            workflow = workflow_factory(settings)
        report = workflow.run(topic, 5)
        paths = save_report(report, settings.report_dir / "NV14" / period / settings.mode / digest)
        store.save_report(report)
        status = "done" if report.complete else "incomplete"
        store.finish_daily(key, owner, status, report.id)
        setup_logging().info("Weekly job %s: %s", status, key)
        return {"status": status, "key": key, "report_id": report.id, "paths": [str(p) for p in paths]}
    except Exception as exc:
        active_provider = provider or getattr(workflow, "provider", None)
        budget = getattr(active_provider, "budget", None)
        calls = getattr(budget, "calls", "n/a")
        limit = getattr(budget, "limit", "n/a")
        logger = setup_logging()
        logger.error(
            "Weekly job diagnostics key=%s mode=%s max_api_calls=%s max_steps=%s "
            "max_rounds=%s timeout=%s api_calls=%s/%s error=%s",
            key, settings.mode, settings.max_api_calls, settings.max_steps,
            settings.max_rounds, settings.timeout, calls, limit,
            exception_summary(exc, (settings.api_key,)),
        )
        log_exception(logger, f"Weekly job failed key={key} mode={settings.mode}", exc, (settings.api_key,))
        try:
            store.finish_daily(key, owner, "failed", error=exception_summary(exc, (settings.api_key,)))
        except Exception as storage_exc:
            log_exception(setup_logging(), "Weekly job failure state update failed; lease may remain active",
                          storage_exc, (settings.api_key,))
        raise
    finally:
        active_provider = provider or (workflow.provider if workflow else None)
        if active_provider:
            try:
                active_provider.close()
            except Exception as exc:
                # Cleanup must not mask the original failure or turn a saved/done
                # report into a CLI failure that cannot safely be retried.
                log_exception(setup_logging(), "Weekly job provider cleanup failed", exc, (settings.api_key,))


# Existing callers remain supported, but they now use weekly semantics.
daily_job = weekly_job
