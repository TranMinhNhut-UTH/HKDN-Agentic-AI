"""Real YouTube Data API v3 collector. No mock fallback or secret-bearing URLs."""
import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import dotenv_values
from shared.config import ROOT

LOCAL_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
API_BASE = "https://www.googleapis.com/youtube/v3/"
ABBREVIATIONS = {
    "ko": "không", "k": "không (cần xét ngữ cảnh)", "kh": "không",
    "k0": "không", "hk": "không", "hok": "không", "khum": "không",
    "dc": "được", "đc": "được", "mn": "mọi người", "mng": "mọi người",
    "mik": "mình", "mk": "mình (cần xét ngữ cảnh)", "vs": "với",
    "ntn": "như thế nào", "nch": "nói chung", "ny": "người yêu",
    "bt": "biết / bình thường (cần xét ngữ cảnh)", "bh": "bây giờ",
    "cx": "cũng", "r": "rồi (cần xét ngữ cảnh)", "trc": "trước",
    "chx": "chưa", "j": "gì", "z": "vậy", "lm": "làm",
    "ns": "nói", "thg": "thương / tháng (cần xét ngữ cảnh)",
}


class YouTubeAPIError(RuntimeError):
    """Safe error containing only status + known reason, never response body/key."""


def key_from_env():
    # User explicitly requested the key in this file, not an ambient env fallback.
    key = (dotenv_values(ROOT / ".env").get("YOUTUBE_API_KEY") or "").strip()
    if not key:
        raise YouTubeAPIError("Thiếu YOUTUBE_API_KEY trong .env")
    return key


def video_id(value):
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    from urllib.parse import urlsplit, parse_qs
    parsed = urlsplit(value)
    if parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        if parsed.path.startswith(("/shorts/", "/embed/")):
            candidate = parsed.path.split("/")[2]
    elif parsed.hostname == "youtu.be":
        candidate = parsed.path.lstrip("/")
    else:
        raise ValueError("URL YouTube không hợp lệ")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise ValueError("Video ID không hợp lệ")
    return candidate


class YouTubeClient:
    def __init__(self, api_key, timeout=20, transport=None):
        # Header instead of query string: key never appears in request URL/error.
        self.client = httpx.Client(timeout=timeout, follow_redirects=False,
                                   headers={"X-Goog-Api-Key": api_key}, transport=transport)
        self.calls = 0

    def close(self):
        self.client.close()

    def get(self, resource, **params):
        if resource not in {"videos", "commentThreads"}:
            raise ValueError("Resource không được phép")
        self.calls += 1
        try:
            response = self.client.get(API_BASE + resource, params=params)
        except httpx.RequestError:
            raise YouTubeAPIError("Không kết nối được YouTube API (network/timeout).") from None
        if response.status_code != 200:
            known = {"keyInvalid", "accessNotConfigured", "quotaExceeded", "dailyLimitExceeded",
                     "commentsDisabled", "videoNotFound", "ipRefererBlocked", "forbidden",
                     "API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED", "API_KEY_HTTP_REFERRER_BLOCKED",
                     "API_KEY_IP_ADDRESS_BLOCKED", "SERVICE_DISABLED"}
            try:
                error = response.json().get("error", {})
                reasons = [item.get("reason") for item in error.get("errors", [])]
                reasons += [item.get("reason") for item in error.get("details", [])]
                reason = next((r for r in reasons if r in known), "unknown")
            except (ValueError, TypeError, AttributeError):
                reason = "unknown"
            raise YouTubeAPIError(f"YouTube API HTTP {response.status_code}; reason={reason}")
        try:
            payload = response.json()
        except ValueError:
            raise YouTubeAPIError("YouTube API trả JSON không hợp lệ") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise YouTubeAPIError("YouTube API trả schema không hợp lệ")
        return payload

    def metadata(self, identifier):
        payload = self.get("videos", part="snippet,statistics,status", id=identifier)
        if not payload["items"]:
            raise YouTubeAPIError("Không tìm thấy video công khai")
        item = payload["items"][0]
        if item.get("status", {}).get("privacyStatus") != "public":
            raise YouTubeAPIError("Video không có trạng thái public")
        return {"id": identifier, "url": "https://www.youtube.com/watch?v=" + identifier,
                "title": item["snippet"]["title"], "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "total_comment_count": int(item.get("statistics", {}).get("commentCount", 0))}

    def collect(self, identifier, limit=100, order="relevance"):
        if not 1 <= limit <= 100:
            raise ValueError("Limit phải từ 1 đến 100")
        if order not in {"time", "relevance"}:
            raise ValueError("Order phải là time hoặc relevance")
        rows, token, seen_tokens = [], None, set()
        while len(rows) < limit:
            params = {"part": "snippet", "videoId": identifier, "maxResults": limit - len(rows),
                      "textFormat": "plainText", "order": order}
            if token:
                params["pageToken"] = token
            payload = self.get("commentThreads", **params)
            for item in payload["items"][:limit - len(rows)]:
                comment = item.get("snippet", {}).get("topLevelComment", {})
                snippet = comment.get("snippet", {})
                rows.append({"comment_id": comment.get("id", ""), "video_id": identifier,
                             "text": snippet.get("textOriginal", snippet.get("textDisplay", "")),
                             "published_at": snippet.get("publishedAt", ""),
                             "updated_at": snippet.get("updatedAt", ""),
                             "like_count": snippet.get("likeCount", 0),
                             "source_url": f"https://www.youtube.com/watch?v={identifier}&lc={comment.get('id', '')}"})
            token = payload.get("nextPageToken")
            if not payload["items"] or not token or token in seen_tokens:
                break
            seen_tokens.add(token)
        return rows


def normalized_text(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def parse_timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp thiếu múi giờ")
    return parsed.astimezone(timezone.utc)


def detect_abbreviations(text):
    # Whole Unicode tokens, case-insensitive. Avoid matches inside ordinary words/URLs.
    text = re.sub(r"https?://\S+", " ", text)
    tokens = re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())
    return Counter(token for token in tokens if token in ABBREVIATIONS)


def process_comments(rows, start=None, end=None, abbreviation_mode="all"):
    if start and end and start > end:
        raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
    if abbreviation_mode not in {"all", "only", "exclude"}:
        raise ValueError("Abbreviation mode không hợp lệ")
    kept, rejected = [], []
    seen_ids, seen_texts = set(), set()
    for row in rows:
        reason = ""
        timestamp = None
        text = row.get("text")
        identifier = row.get("comment_id")
        if not isinstance(text, str) or not text.strip() or not isinstance(identifier, str) or not identifier:
            reason = "invalid_content_or_id"
        else:
            try:
                timestamp = parse_timestamp(row["published_at"])
            except (ValueError, TypeError, AttributeError, KeyError):
                reason = "invalid_date"
        if not reason:
            local_day = timestamp.astimezone(LOCAL_ZONE).date()
            if (start and local_day < start) or (end and local_day > end):
                reason = "outside_date_range"
        if not reason:
            signature = normalized_text(text)
            if identifier in seen_ids:
                reason = "duplicate_id"
            elif signature in seen_texts:
                reason = "duplicate_text"
            else:
                seen_ids.add(identifier)
                seen_texts.add(signature)
        if reason:
            rejected.append({**row, "rejection_reason": reason})
            continue
        hits = detect_abbreviations(text)
        if (abbreviation_mode == "only" and not hits) or (abbreviation_mode == "exclude" and hits):
            rejected.append({**row, "rejection_reason": "abbreviation_filter"})
            continue
        kept.append({**row, "published_local": timestamp.astimezone(LOCAL_ZONE).isoformat(),
                     "abbreviations": "; ".join(f"{term}:{count}" for term, count in sorted(hits.items())),
                     "abbreviation_count": sum(hits.values())})
    return kept, rejected


CSV_FIELDS = ["comment_id", "video_id", "published_at", "published_local", "updated_at", "like_count",
              "text", "abbreviations", "abbreviation_count", "source_url", "rejection_reason"]


def csv_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: csv_safe(v) for k, v in row.items()} for row in rows)


def collect_and_export(identifier, limit=100, order="relevance", start=None, end=None,
                       abbreviation_mode="all", output_root=None):
    identifier = video_id(identifier)
    if start and end and start > end:
        raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
    client = YouTubeClient(key_from_env())
    try:
        metadata = client.metadata(identifier)
        rows = client.collect(identifier, limit, order)
        api_calls = client.calls
    finally:
        client.close()
    valid, rejected = process_comments(rows, start, end, abbreviation_mode)
    all_valid, all_rejected = process_comments(rows)
    abbreviations_only, _ = process_comments(rows, abbreviation_mode="only")
    excluded, _ = process_comments(rows, abbreviation_mode="exclude")
    terms = Counter()
    for row in all_valid:
        terms.update(detect_abbreviations(row["text"]))
    # Exercise date filtering using real collected rows, latest observed calendar day.
    latest_day = max((date.fromisoformat(row["published_local"][:10]) for row in all_valid), default=None)
    date_subset, date_rejected = process_comments(rows, latest_day, latest_day) if latest_day else ([], [])
    replay, replay_rejected = process_comments(rows + rows)
    checks = {
        "abbreviation_partition": len(abbreviations_only) + len(excluded) == len(all_valid),
        "abbreviation_only_has_hits": all(r["abbreviation_count"] > 0 for r in abbreviations_only),
        "abbreviation_exclude_has_no_hits": all(r["abbreviation_count"] == 0 for r in excluded),
        "date_filter_latest_day": all(r["published_local"][:10] == str(latest_day) for r in date_subset),
        "date_filter_reconciles": len(date_subset) + len(date_rejected) == len(rows),
        "dedup_replay_same_ids": [r["comment_id"] for r in replay] == [r["comment_id"] for r in all_valid],
        "dedup_replay_removed": len(replay_rejected) == len(all_rejected) + len(rows),
    }
    if not all(checks.values()):
        raise RuntimeError("Kiểm tra filter dữ liệu thực không đạt")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(output_root or ROOT / "reports/YouTube") / f"{identifier}_{stamp}"
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "raw.json").write_text(json.dumps({"video": metadata, "comments": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    outputs = {"raw.csv": rows, "valid.csv": valid, "rejected.csv": rejected,
               "abbreviations_only.csv": abbreviations_only, "abbreviations_excluded.csv": excluded,
               "latest_day.csv": date_subset}
    for filename, records in outputs.items():
        export_csv(folder / filename, records)
        with (folder / filename).open(encoding="utf-8-sig", newline="") as handle:
            loaded = list(csv.DictReader(handle))
        if len(loaded) != len(records) or any(loaded_row["text"] != csv_safe(original["text"])
                                              for loaded_row, original in zip(loaded, records)):
            raise RuntimeError("CSV round-trip không khớp dữ liệu thật")
    summary = {
        "mode": "live", "collected_at": datetime.now(timezone.utc).isoformat(), "video": metadata,
        "order": order, "api_calls": api_calls, "collected": len(rows), "valid": len(valid),
        "valid_before_optional_filters": len(all_valid), "rejected": len(rejected),
        "rejection_counts": dict(Counter(r["rejection_reason"] for r in rejected)),
        "natural_duplicates_removed": sum(r["rejection_reason"].startswith("duplicate_") for r in all_rejected),
        "comments_with_abbreviations": len(abbreviations_only), "abbreviation_occurrences": sum(terms.values()),
        "distinct_abbreviations": len(terms), "abbreviation_terms": dict(terms.most_common()),
        "date_filter": {"timezone": "Asia/Ho_Chi_Minh", "from": str(start) if start else None,
                        "to": str(end) if end else None, "test_day": str(latest_day) if latest_day else None,
                        "test_kept": len(date_subset), "test_removed": len(date_rejected)},
        "abbreviation_mode": abbreviation_mode, "checks": {**checks, "csv_round_trip": True},
        "files": {name: str((folder / name).resolve()) for name in [*outputs, "raw.json"]},
        "limitations": ["Chỉ bình luận cấp đầu, không thu thập replies.",
                         "Từ viết tắt theo từ điển/rule; một số token cần xét ngữ cảnh, không phải phân loại chắc chắn.",
                         "Lọc ngày cục bộ trong mẫu tối đa 100, không tìm toàn bộ lịch sử video.",
                         "Replay dedup dùng lại các bản ghi thật trong bộ nhớ; không thêm dữ liệu giả vào file xuất.",
                         "CSV chặn formula bằng apostrophe khi cần; raw.json giữ text nguyên bản."]}
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
