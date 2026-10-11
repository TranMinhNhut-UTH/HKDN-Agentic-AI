"""SDK schema/transport contract tests; no real Gemini request is sent."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx
import pytest
from google import genai
from google.genai import types
from shared.config import Settings
from shared.llm import GeminiProvider
from shared.models import Plan, Analysis
from shared.rss import RSSReader, normalize


def live_settings():
    return Settings(mode="live", api_key="unit-test-placeholder-not-a-real-key")


def provider(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)
    return GeminiProvider(live_settings()), client


def test_gemini_function_call_and_response_history(monkeypatch):
    llm, client = provider(monkeypatch)
    call = types.FunctionCall(name="fetch_rss", args={"source": "bbc"})
    content = types.Content(role="model", parts=[types.Part(function_call=call)])
    client.models.generate_content.return_value = SimpleNamespace(function_calls=[call], candidates=[SimpleNamespace(content=content)])
    history = []
    name, args, returned = llm.collect({"topic": "AI", "count": 5, "attempted": [], "articles": []}, history)
    assert name == "fetch_rss" and args == {"source": "bbc"}
    llm.observe(history, returned, name, {"articles": []})
    assert [c.role for c in history] == ["user", "model", "user"]
    assert history[-1].parts[0].function_response.name == "fetch_rss"
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.automatic_function_calling.disable
    assert str(config.tool_config.function_calling_config.mode).endswith("ANY")
    assert len(config.tools[0].function_declarations) == 2
    llm.close()
    client.close.assert_called_once()


def test_gemini_structured_json_and_invalid_output(monkeypatch):
    llm, client = provider(monkeypatch)
    client.models.generate_content.return_value = SimpleNamespace(text=Plan(topic="AI", count=5, tool="news_workflow", rationale="test").model_dump_json())
    assert llm.plan("5 tin AI").count == 5
    assert client.models.generate_content.call_args.kwargs["config"].response_mime_type == "application/json"
    client.models.generate_content.return_value = SimpleNamespace(text='{"tool":"shell","count":100}')
    with pytest.raises(ValueError):
        llm.plan("invalid")


def test_live_rss_transport_timeout_and_normalization(monkeypatch):
    captured = []
    real_client = httpx.Client
    def transport(request):
        captured.append(str(request.url))
        return httpx.Response(200, content=b'''<rss version="2.0"><channel><title>Test</title><item>
          <title>Real transport fixture AI</title><link>https://example.org/news?utm_source=rss</link>
          <description>AI research excerpt</description><pubDate>Thu, 01 Jan 2026 08:00:00 GMT</pubDate>
          </item></channel></rss>''')
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    articles = RSSReader(live_settings()).fetch("bbc")
    assert captured == ["https://feeds.bbci.co.uk/news/technology/rss.xml"]
    assert len(articles) == 1 and not articles[0].simulated
    assert articles[0].published == "2026-01-01T08:00:00+00:00"
    assert str(articles[0].url) == "https://example.org/news"


def test_rss_bad_http_and_no_mock_fallback(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda req: httpx.Response(503)), **kwargs))
    with pytest.raises(httpx.HTTPStatusError):
        RSSReader(live_settings()).fetch("bbc")


def test_date_invalid_and_iso():
    item = {"title": "AI", "link": "https://example.org/news", "published": "not a date"}
    assert normalize(item, "test").published is None
    item["published"] = "2026-01-01"
    assert normalize(item, "test").published == "2026-01-01T00:00:00+00:00"
