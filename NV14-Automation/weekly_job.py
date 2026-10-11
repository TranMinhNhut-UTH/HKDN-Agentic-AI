import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.automation import weekly_job
from shared.config import Settings
from shared.config import setup_logging
from shared.diagnostics import exception_summary, log_exception


def main(argv=None):
    parser = argparse.ArgumentParser(description="NV14: 5 tin AI/tuần, tuần ISO theo Asia/Ho_Chi_Minh")
    parser.add_argument("--topic", default="AI")
    # Override APP_MODE only for NV14; other assignments keep their own defaults.
    parser.add_argument("--mode", choices=["mock", "live"], default="live")
    args = parser.parse_args(argv)
    settings = None
    try:
        settings = Settings.load(args.mode)
        result = weekly_job(settings, args.topic)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["status"] == "incomplete" else 0
    except Exception as exc:
        secrets = (settings.api_key,) if settings else ()
        # Configuration/claim errors occur before weekly_job's own try block.
        # This also records a safe CLI traceback if job logging itself failed.
        log_exception(setup_logging(), "NV14 CLI failed", exc, secrets)
        print(f"Weekly job thất bại: {exception_summary(exc, secrets)}; xem logs/agents.log", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
