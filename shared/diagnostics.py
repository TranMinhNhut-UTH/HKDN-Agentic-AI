"""Error diagnostics without raw request/response bodies or traceback locals."""
import re
import traceback
from urllib.parse import quote, quote_plus
from google.genai.errors import APIError


def redact(text, secrets=()):
    text = str(text)
    for secret in secrets:
        if secret:
            for value in {secret, quote(secret, safe=""), quote_plus(secret)}:
                text = text.replace(value, "[REDACTED]")
    text = re.sub(r"AIza[\w-]{20,}", "[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[^\s\"',}]+", "Bearer [REDACTED]", text)
    text = re.sub(
        r'''(?ix)(\b(?:key|api[_-]?key|gemini_api_key|youtube_api_key|x-goog-api-key|authorization|access_token|refresh_token|token|password|client_secret)\b["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s&,}\]]+)''',
        r"\1[REDACTED]", text)
    return text


def http_status(exc):
    code = getattr(exc, "code", None)
    if not isinstance(code, int):
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return code if isinstance(code, int) and 100 <= code <= 599 else None


def exception_summary(exc, secrets=()):
    # Gemini APIError.message contains the useful message, unlike str(APIError)
    # which can serialize the entire response body.
    message = getattr(exc, "message", None)
    if not isinstance(message, str):
        message = "API did not provide an error message" if isinstance(exc, APIError) else str(exc)
    message = redact(message, secrets).replace("\r", " ").replace("\n", " ")[:1500]
    return f"{type(exc).__name__} HTTP={http_status(exc) or 'n/a'} message={message}"


def safe_traceback(exc, secrets=()):
    lines, seen = [], set()
    def visit(error, depth=0):
        if id(error) in seen or depth >= 8:
            return
        seen.add(id(error))
        previous = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        if previous:
            visit(previous, depth + 1)
            lines.append("During handling of the preceding exception:\n")
        lines.append("Traceback (most recent call last):\n")
        # No frame locals, request object, headers, or raw error response are logged.
        lines.extend(traceback.format_list(traceback.extract_tb(error.__traceback__)))
        lines.append(exception_summary(error, secrets) + "\n")
    visit(exc)
    return redact("".join(lines), secrets)


def log_exception(logger, context, exc, secrets=()):
    # Sanitize before creating the LogRecord, so every handler receives safe text.
    logger.error("%s: %s\n%s", context, exception_summary(exc, secrets), safe_traceback(exc, secrets))
