from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class Article(BaseModel):
    id: str
    title: str
    url: HttpUrl
    source: str
    excerpt: str
    published: str | None = None
    simulated: bool = False


class Finding(BaseModel):
    article_id: str
    category: str
    summary: str
    evidence_quote: str
    confidence: Literal["low", "medium"] = "low"
    limitation: str = "Chỉ có dữ liệu RSS; chưa xác minh độc lập toàn văn."


class Analysis(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    needs_more: bool = False
    followup_topic: str = ""
    reason: str


class Plan(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    count: int = Field(ge=1, le=20)
    tool: Literal["news_workflow"]
    rationale: str


class Evaluation(BaseModel):
    revise: bool
    topic: str = ""
    reason: str


class Report(BaseModel):
    id: str
    topic: str
    requested_count: int
    mode: Literal["mock", "live"]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    articles: list[Article]
    analysis: Analysis
    steps: list[dict]
    api_calls: int
    complete: bool
    warning: str = ""
