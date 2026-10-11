from shared.agents import NewsWorkflow, Trace, save_report
from shared.llm import make_provider, BudgetExceeded
from shared.diagnostics import exception_summary, log_exception


def execute_request(settings, store, run_id, request, provider_factory=None):
    provider = None
    trace = Trace(callback=lambda steps: store.update_run(run_id, steps=steps))
    store.update_run(run_id, status="running")
    try:
        provider = provider_factory(settings) if provider_factory else make_provider(settings, retry_attempts=3)
        plan = provider.plan(request)
        trace.emit("Planner", "plan", plan.model_dump(mode="json"))
        # Planner tool dispatcher, restricted to the single approved workflow.
        if plan.tool != "news_workflow":
            raise ValueError("Planner chọn tool không được phép")
        report = None
        for attempt in range(2):
            workflow = NewsWorkflow(settings, provider=provider, trace=trace)
            try:
                report = workflow.run(plan.topic, plan.count)
                evaluation = provider.evaluate(request, report)
            except BudgetExceeded:
                if report is None:
                    raise
                report.complete = False
                report.warning = "Đạt giới hạn gọi model; giữ báo cáo có căn cứ gần nhất."
                trace.emit("Coordinator", "budget_limit", report.warning)
                break
            trace.emit("Planner", "evaluate", evaluation.model_dump(mode="json"))
            if not evaluation.revise:
                break
            if attempt == 0:
                plan.topic = evaluation.topic.strip()[:300] or plan.topic
                trace.emit("Planner", "revise", plan.model_dump(mode="json"))
            else:
                report.complete = False
                report.warning = "Planner chưa xác nhận đáp ứng yêu cầu sau 2 lượt kế hoạch; " + report.warning
        trace.emit("Coordinator", "finished", "Hoàn thành" if report.complete else "Kết quả chưa đủ căn cứ")
        report.steps = trace.steps.copy()
        report.api_calls = provider.budget.calls
        save_report(report, settings.report_dir / "NV15")
        store.save_report(report)
        store.update_run(run_id, status="completed" if report.complete else "incomplete", report_id=report.id)
    except Exception as exc:
        summary = exception_summary(exc, (settings.api_key,))
        log_exception(trace.logger, f"NV15 failed run={run_id} mode={settings.mode}", exc, (settings.api_key,))
        trace.emit("Coordinator", "failed", summary)
        store.update_run(run_id, status="failed", error=summary + "; xem logs/agents.log để biết vị trí lỗi.")
    finally:
        if provider:
            try:
                provider.close()
            except Exception as exc:
                log_exception(trace.logger, f"NV15 provider cleanup failed run={run_id}", exc, (settings.api_key,))
