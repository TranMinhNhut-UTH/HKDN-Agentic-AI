import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from shared.config import Settings
from shared.web import create_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NV15: local web app")
    parser.add_argument("--mode", choices=["mock", "live"])
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(Settings.load(args.mode)), host="127.0.0.1", port=args.port, workers=1)
