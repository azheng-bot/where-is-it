from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("DATABASE_PATH", "services/api/data/where-is-it.db"))
    evidence_dir: Path = Path(os.getenv("EVIDENCE_DIR", "services/api/data/evidence"))
    evidence_max_per_object: int = int(os.getenv("EVIDENCE_MAX_PER_OBJECT", "20"))
    evidence_max_bytes: int = int(os.getenv("EVIDENCE_MAX_BYTES", str(512 * 1024 * 1024)))
    freshness_seconds: int = int(os.getenv("FRESHNESS_SECONDS", "3"))
    missing_grace_seconds: int = int(os.getenv("MISSING_GRACE_SECONDS", "5"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "2.5"))


settings = Settings()
