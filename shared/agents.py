import json
import uuid
from pathlib import Path
from shared.config import setup_logging
from shared.llm import make_provider
from shared.models import Report
from shared.rss import RSSReader, SOURCES, deduplicate


class Trace:
    def __init__(self, callback=None):
        self.steps = []
        self.callback = callback
        self.logger = setup_logging()

    def emit(self, agent, action, detail):
        step = {"step": len(self.steps) + 1, "agent": agent, "action": action, "detail": detail}
        self.steps.append(step)
        self.logger.info("%s %s %s", agent, action, detail)
        if self.callback:
            self.callback(self.steps.copy())


class CollectorAgent:
    def __init__(self, provider, reader, settings, trace):
        self.provider, self.reader, self.settings, self.trace = provider, reader, settings, trace

    def run(self, topic, count, existing=None):
        articles = list(existing or [])
        attempted, history = [], []
        for _ in range(self.settings.max_steps):
            name, args, content = self.provider.collect(
                {"topic": topic, "count": count, "attempted": attempted, "articles": articles}, history)
            if name == "finish_collection":
                ids = args.get("article_ids", [])
                if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                    raise ValueError("Danh sÃ¡ch ID khÃ´ng há»£p lá»‡")
                if set(ids) - {a.id for a in articles}:
                    raise ValueError("Collector Ä‘á» xuáº¥t ID khÃ´ng tá»“n táº¡i")
                chosen = [a for a in articles if a.id in ids][:count]
                self.trace.emit("Collector", "finish", str(args.get("rationale", ""))[:1000])
                return chosen
            if name != "fetch_rss" or args.get("source") not in SOURCES:
                raise ValueError("Function call khÃ´ng Ä‘Æ°á»£c phÃ©p")
            source = args["source"]
            if source in attempted:
                self.trace.emit("Collector", "skip", "Nguá»“n Ä‘Ã£ Ä‘á»c: " + source)
                self.provider.observe(history, content, name, {"error": "source already attempted"})
                continue
            attempted.append(source)
            try:
                fetched = self.reader.fetch(source)
                articles = deduplicate(articles + fetched)
                result = {"articles": [a.model_dump(mode="json") for a in fetched]}
                self.trace.emit("Collector", "fetch_rss", f"{source}: {len(fetched)} bÃ i")
            except Exception as exc:
                # Do not expose request headers or API credentials to logs/model.
                result = {"error": type(exc).__name__, "source": source}
                self.trace.emit("Collector", "source_error", f"{source}: {type(exc).__name__}; thá»­ nguá»“n khÃ¡c")
            self.provider.observe(history, content, name, result)
        raise RuntimeError("Collector Ä‘áº¡t giá»›i háº¡n bÆ°á»›c trÆ°á»›c khi chá»n bÃ i")


class AnalystAgent:
    def __init__(self, provider, trace):
        self.provider, self.trace = provider, trace

    def run(self, topic, count, articles):
        analysis = self.provider.analyze(topic, count, articles)
        by_id = {a.id: a for a in articles}
        valid, seen, rejected = [], set(), 0
        for finding in analysis.findings:
            a = by_id.get(finding.article_id)
            quote = finding.evidence_quote.strip()
            if not a or a.id in seen or not quote or not (quote in a.excerpt or quote in a.title):
                rejected += 1
                continue
            seen.add(a.id)
            # Model cannot remove this evidence limitation.
            finding.limitation = ("MOCK: dá»¯ liá»‡u mÃ´ phá»ng. " if a.simulated else "") + "Chá»‰ cÃ³ trÃ­ch Ä‘oáº¡n RSS; chÆ°a xÃ¡c minh Ä‘á»™c láº­p toÃ n vÄƒn."
            valid.append(finding)
        analysis.findings = valid
        if rejected or len(valid) < count:
            analysis.needs_more = True
            analysis.reason += f"; kiá»ƒm tra cÄƒn cá»©: {rejected} má»¥c bá»‹ loáº¡i, {len(valid)}/{count} má»¥c há»£p lá»‡"
        self.trace.emit("Analyst", "analyze", analysis.reason[:1000])
        return analysis


class NewsWorkflow:
    def __init__(self, settings, provider=None, reader=None, trace=None):
        self.settings = settings
        self.provider = provider or make_provider(settings)
        self.trace = trace or Trace()
        self.collector = CollectorAgent(self.provider, reader or RSSReader(settings), settings, self.trace)
        self.analyst = AnalystAgent(self.provider, self.trace)

    def run(self, topic, count=5):
        if not topic.strip() or len(topic) > 300 or not 1 <= count <= 20:
            raise ValueError("Chá»§ Ä‘á» pháº£i dÃ i 1-300 kÃ½ tá»±; sá»‘ tin tá»« 1 Ä‘áº¿n 20")
        articles, search_topic = [], topic
        for round_index in range(self.settings.max_rounds):
            self.trace.emit("Coordinator", "round", f"VÃ²ng {round_index + 1}/{self.settings.max_rounds}; mode={self.settings.mode}")
            articles = self.collector.run(search_topic, count, articles)
            analysis = self.analyst.run(topic, count, articles)
            if not analysis.needs_more:
                break
            search_topic = analysis.followup_topic.strip()[:300] or topic
            self.trace.emit("Analyst", "request_more", search_topic)
        complete = len(analysis.findings) >= count and not analysis.needs_more
        return Report(id=uuid.uuid4().hex, topic=topic, requested_count=count, mode=self.settings.mode,
                      articles=articles, analysis=analysis, steps=self.trace.steps.copy(),
                      api_calls=self.provider.budget.calls, complete=complete,
                      warning="" if complete else "ChÆ°a Ä‘á»§ tin/cÄƒn cá»© trong giá»›i háº¡n xá»­ lÃ½; khÃ´ng bá»‹a thÃªm dá»¯ liá»‡u.")


def markdown(report):
    lines = [f"# Báº£n tin: {report.topic}", "", f"Cháº¿ Ä‘á»™: **{report.mode.upper()}**",
             f"Thá»i Ä‘iá»ƒm UTC: {report.created_at}", f"Káº¿t quáº£: {len(report.analysis.findings)}/{report.requested_count}",
             "", "Dá»® LIá»†U MÃ” PHá»ŽNG â€” khÃ´ng pháº£i tin tháº­t." if report.mode == "mock" else "Nguá»“n RSS; chÆ°a xÃ¡c minh Ä‘á»™c láº­p toÃ n vÄƒn.", report.warning, ""]
    by_id = {a.id: a for a in report.articles}
    for f in report.analysis.findings:
        a = by_id[f.article_id]
        lines.extend([f"## {a.title}", f"- PhÃ¢n loáº¡i: {f.category}", f"- TÃ³m táº¯t: {f.summary}",
                      f"- Báº±ng chá»©ng: {f.evidence_quote}", f"- Giá»›i háº¡n: {f.limitation}",
                      f"- Nguá»“n: {a.source} â€” {a.url}", ""])
    lines.extend(["## Trace", "```json", json.dumps(report.steps, ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines)


def save_report(report, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for extension, text in (("json", report.model_dump_json(indent=2)), ("md", markdown(report))):
        path = folder / f"{report.id}.{extension}"
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)
        paths.append(path)
    return paths
