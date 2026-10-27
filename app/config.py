from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    secret_key: str
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    storage_dir: Path
    max_upload_bytes: int = 8 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        return cls(
            secret_key=os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me"),
            openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
            openai_base_url=base_url,
            storage_dir=Path(os.environ.get("STORAGE_DIR", ROOT / "storage")),
        )

    @property
    def chat_enabled(self) -> bool:
        return bool(self.openai_api_key)
