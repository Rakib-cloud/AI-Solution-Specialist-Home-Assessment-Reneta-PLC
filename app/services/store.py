from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.models import PolicyDocument

_ID = re.compile(r"^[a-f0-9]{32}$")


class PolicyStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, policy: PolicyDocument, pdf_bytes: bytes) -> None:
        folder = self._folder(policy.id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "source.pdf").write_bytes(pdf_bytes)
        (folder / "policy.json").write_text(json.dumps(policy.to_dict(), indent=2), encoding="utf-8")

    def save_analysis(self, policy_id: str, quotes: list[dict], warning: str | None) -> None:
        if not _ID.match(policy_id or ""):
            return
        path = self._folder(policy_id) / "analysis.json"
        path.write_text(
            json.dumps({"quotes": quotes, "warning": warning}, indent=2),
            encoding="utf-8",
        )

    def load_analysis(self, policy_id: str) -> dict:
        if not _ID.match(policy_id or ""):
            return {"quotes": [], "warning": None}
        path = self._folder(policy_id) / "analysis.json"
        if not path.is_file():
            return {"quotes": [], "warning": None}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"quotes": data.get("quotes") or [], "warning": data.get("warning")}

    def load(self, policy_id: str) -> PolicyDocument | None:
        if not _ID.match(policy_id or ""):
            return None
        path = self._folder(policy_id) / "policy.json"
        if not path.is_file():
            return None
        return PolicyDocument.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _folder(self, policy_id: str) -> Path:
        return self.root / "policies" / policy_id
