from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[3]

def _load_dotenv() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()
@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "services" / "api" / "data" / "mock-where-is-it.db")))
    evidence_dir: Path = Path(os.getenv("EVIDENCE_DIR", str(PROJECT_ROOT / "services" / "api" / "data" / "evidence")))
    evidence_max_per_object: int = int(os.getenv("EVIDENCE_MAX_PER_OBJECT", "20"))
    evidence_max_bytes: int = int(os.getenv("EVIDENCE_MAX_BYTES", str(512 * 1024 * 1024)))
    freshness_seconds: int = int(os.getenv("FRESHNESS_SECONDS", "3"))
    missing_grace_seconds: int = int(os.getenv("MISSING_GRACE_SECONDS", "5"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "2.5"))
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    vision_public_url: str = os.getenv("VISION_PUBLIC_URL", "http://127.0.0.1:8001").rstrip("/")


settings = Settings()
