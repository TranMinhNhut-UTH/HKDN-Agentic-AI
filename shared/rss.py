"""Allowlisted RSS only. No LLM-provided URL is fetched."""
import hashlib
import html
import json
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import feedparser
import httpx
from shared.config import ROOT, Settings
from shared.models import Article

SOURCES = {
    "bbc": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "techcrunch": "https://techcrunch.com/feed/",
    "verge": "https://www.theverge.com/rss/index.xml",
}


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def canonical_url(url):
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("URL bài viết không hợp lệ")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query)
                             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}))
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", query, ""))


def normalize(entry, source, simulated=False):
    url = canonical_url(entry.get("link", ""))
    title = clean(entry.get("title", ""))[:500]
    if not title:
        raise ValueError("Thiếu tiêu đề")
    published = None
    raw_date = entry.get("published")
    if raw_date:
        try:
            try:
                value = parsedate_to_datetime(raw_date)
            except ValueError:
                value = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            published = value.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError, AttributeError, OverflowError):
            pass
    return Article(id=hashlib.sha256(url.encode()).hexdigest()[:20], title=title,
                   url=url, source=source, excerpt=clean(entry.get("summary", ""))[:4000],
                   published=published, simulated=simulated)


def deduplicate(articles):
    seen_urls, seen_titles, result = set(), set(), []
    for a in articles:
        key = clean(a.title).casefold()
        if str(a.url) not in seen_urls and key not in seen_titles:
            result.append(a)
            seen_urls.add(str(a.url))
            seen_titles.add(key)
    return result


def filter_articles(articles, topic):
    tokens = set(re.findall(r"\w+", topic.casefold())) - {"tin", "về", "news", "the", "and", "mới", "nhất"}
    scored = [(sum(t in (a.title + " " + a.excerpt).casefold() for t in tokens), a) for a in articles]
    return [a for score, a in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0]


class RSSReader:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch(self, source):
        if source not in SOURCES:
            raise ValueError("Nguồn RSS không thuộc allowlist")
        if self.settings.mode == "mock":
            data = json.loads((ROOT / "samples/articles.json").read_text(encoding="utf-8"))
            return [normalize(e, source, True) for e in data if e["source"] == source]
        # Stream with a size cap; redirects are not followed to untrusted hosts.
        with httpx.Client(timeout=self.settings.timeout, follow_redirects=False) as client:
            with client.stream("GET", SOURCES[source], headers={"User-Agent": "LocalNewsIntelligence/1.0"}) as r:
                r.raise_for_status()
                chunks, size = [], 0
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError("RSS vượt giới hạn 2MB")
                    chunks.append(chunk)
        parsed = feedparser.parse(b"".join(chunks))
        if parsed.bozo and not parsed.entries:
            raise ValueError("RSS không đọc được")
        result = []
        for entry in parsed.entries[:100]:
            try:
                result.append(normalize(entry, source))
            except (ValueError, TypeError):
                logging.getLogger("news").warning("Bỏ qua entry RSS không hợp lệ: %s", source)
        return deduplicate(result)
