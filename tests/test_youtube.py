import csv
from datetime import date
import httpx
import pytest
from shared.youtube import (YouTubeClient, YouTubeAPIError, detect_abbreviations,
                            process_comments, export_csv, video_id)


def row(identifier="a", text="MN ko biết, đc rồi", published="2026-01-01T18:00:00Z"):
    return {"comment_id": identifier, "text": text, "published_at": published}


def test_abbreviations_unicode_boundaries():
    hits = detect_abbreviations("MN ko KO ĐC; không biết karaoke. https://example.org/ko")
    assert hits == {"mn": 1, "ko": 2, "đc": 1}
    assert not detect_abbreviations("không biết karaoke")


def test_date_inclusive_vietnam_timezone():
    rows = [row(), row("b", "khác", "2026-01-01T16:59:59Z")]
    valid, rejected = process_comments(rows, date(2026, 1, 2), date(2026, 1, 2))
    assert [r["comment_id"] for r in valid] == ["a"]
    assert rejected[0]["rejection_reason"] == "outside_date_range"
    with pytest.raises(ValueError):
        process_comments(rows, date(2026, 1, 2), date(2026, 1, 1))


def test_duplicate_ids_text_and_invalid():
    rows = [row(), row(text="khác"), row("b", " mn KO biết, đc rồi  "), row("c", ""), row("d", "abc", "bad")]
    valid, rejected = process_comments(rows)
    assert len(valid) == 1
    assert [r["rejection_reason"] for r in rejected] == ["duplicate_id", "duplicate_text", "invalid_content_or_id", "invalid_date"]


def test_abbreviation_filter_modes():
    rows = [row(), row("b", "bài hát rất hay")]
    assert len(process_comments(rows, abbreviation_mode="only")[0]) == 1
    assert len(process_comments(rows, abbreviation_mode="exclude")[0]) == 1


def test_date_filter_before_text_dedup():
    rows = [row("older", "hay", "2026-01-01T00:00:00Z"), row("newer", "hay", "2026-01-02T00:00:00Z")]
    valid, rejected = process_comments(rows, date(2026, 1, 2), date(2026, 1, 2))
    assert [r["comment_id"] for r in valid] == ["newer"]
    assert rejected[0]["rejection_reason"] == "outside_date_range"


def test_csv_unicode_newline_formula_round_trip(tmp_path):
    path = tmp_path / "comments.csv"
    export_csv(path, [row(text='=1+1\n"tiếng Việt", vui')])
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    assert records[0]["text"] == '\'=1+1\n"tiếng Việt", vui'


def test_api_header_pagination_cap():
    requests = []
    def transport(request):
        requests.append(request)
        count = int(request.url.params["maxResults"])
        items = [{"snippet": {"topLevelComment": {"id": str(len(requests)) + str(i),
                  "snippet": {"textOriginal": "real API contract fixture", "publishedAt": "2026-01-01T00:00:00Z"}}}} for i in range(min(count, 60))]
        return httpx.Response(200, json={"items": items, "nextPageToken": "next"})
    client = YouTubeClient("test-secret", transport=httpx.MockTransport(transport))
    assert len(client.collect("ukHK1GVyr0I", 100)) == 100
    assert [r.url.params["maxResults"] for r in requests] == ["100", "40"]
    assert all("test-secret" not in str(r.url) and r.headers["X-Goog-Api-Key"] == "test-secret" for r in requests)
    client.close()


def test_api_error_never_echoes_secret():
    client = YouTubeClient("test-secret", transport=httpx.MockTransport(lambda req: httpx.Response(
        403, json={"error": {"message": "test-secret", "errors": [{"reason": "accessNotConfigured"}]}})))
    with pytest.raises(YouTubeAPIError) as caught:
        client.metadata("ukHK1GVyr0I")
    assert "test-secret" not in str(caught.value) and "accessNotConfigured" in str(caught.value)
    client.close()


def test_video_url_validation():
    assert video_id("https://www.youtube.com/watch?v=ukHK1GVyr0I") == "ukHK1GVyr0I"
    with pytest.raises(ValueError):
        video_id("https://evil.example/watch?v=ukHK1GVyr0I")
