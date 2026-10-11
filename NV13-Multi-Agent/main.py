"""Independent NV13 entry point; shared source remains at repository root."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.agents import NewsWorkflow, save_report
from shared.config import Settings, setup_logging


def main():
    parser = argparse.ArgumentParser(description="NV13: Collector + Analyst")
    parser.add_argument("--topic", default="AI")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--mode", choices=["mock", "live"])
    args = parser.parse_args()
    workflow = None
    try:
        settings = Settings.load(args.mode)
        workflow = NewsWorkflow(settings)
        report = workflow.run(args.topic, args.count)
        paths = save_report(report, settings.report_dir / "NV13")
        print(f"mode={report.mode}; complete={report.complete}; findings={len(report.analysis.findings)}")
        for path in paths:
            print(path)
        return 0 if report.complete else 2
    except Exception as exc:
        setup_logging().error("NV13 thất bại: %s", type(exc).__name__)
        print(f"Lỗi {type(exc).__name__}; kiểm tra cấu hình, quota hoặc giới hạn xử lý.", file=sys.stderr)
        return 1
    finally:
        if workflow:
            workflow.provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
