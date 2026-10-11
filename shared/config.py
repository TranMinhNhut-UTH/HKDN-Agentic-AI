from dataclasses import dataclass
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    mode: str = "mock"
    api_key: str = ""
    model: str = "gemini-flash-latest"
    timeout: float = 20
    max_api_calls: int = 16
    max_steps: int = 8
    max_rounds: int = 2
    data_dir: Path = ROOT / "data"
    report_dir: Path = ROOT / "reports"

    def __post_init__(self):
        if self.mode not in {"mock", "live"}:
            raise ValueError("APP_MODE phải là mock hoặc live")
        if self.mode == "live" and not self.api_key:
            raise ValueError("Chế độ live cần GEMINI_API_KEY; không tự chuyển sang mock")
        if min(self.timeout, self.max_api_calls, self.max_steps, self.max_rounds) <= 0:
            raise ValueError("Các giới hạn phải lớn hơn 0")
        self.data_dir = Path(self.data_dir)
        self.report_dir = Path(self.report_dir)

    @classmethod
    def load(cls, mode=None):
        load_dotenv(ROOT / ".env")
        return cls(
            mode=mode or os.getenv("APP_MODE", "mock"),
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            timeout=float(os.getenv("HTTP_TIMEOUT", "20")),
            max_api_calls=int(os.getenv("MAX_API_CALLS", "16")),
            max_steps=int(os.getenv("MAX_STEPS", "8")),
            max_rounds=int(os.getenv("MAX_ROUNDS", "2")),
            data_dir=ROOT / os.getenv("DATA_DIR", "data"),
            report_dir=ROOT / os.getenv("REPORT_DIR", "reports"),
        )


def setup_logging():
    folder = ROOT / "logs"
    folder.mkdir(exist_ok=True)
    logger = logging.getLogger("news")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for handler in (logging.StreamHandler(), RotatingFileHandler(
                folder / "agents.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")):
            handler.setFormatter(fmt)
            logger.addHandler(handler)
    return logger
