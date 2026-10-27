from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import ROOT
from app.services.authored import SAMPLE_POLICY_ID, _section, _sub
from app.services.extractor import META_RE, extract_policy, read_role_rows

_SAMPLE_PDF = ROOT / "XYZ Company Leave Policy (Sample).pdf"
_CACHED: dict | None = None
_CLAUSE = re.compile(r"(?:^|\s)\(([a-z])\)\s+")
_CLOSING = re.compile(r"\s*End of policy\..*$", re.IGNORECASE)


def sample_draft() -> dict | None:
    global _CACHED
    if _CACHED is None:
        if not _SAMPLE_PDF.is_file():
            return None
        _CACHED = draft_from_pdf(_SAMPLE_PDF, _SAMPLE_PDF.name, status="draft")
        _CACHED.pop("id", None)
    return json.loads(json.dumps(_CACHED))


def ensure_sample_policy(storage: Path) -> None:
    from app.services.authored import DraftStore, sanitize

    root = Path(storage)
    marker = root / ".sample-seeded"
    store = DraftStore(root)
    if store.load(SAMPLE_POLICY_ID) or marker.is_file():
        return
    draft = sample_draft()
    if draft is None:
        return
    draft["id"] = SAMPLE_POLICY_ID
    draft["status"] = "published"
    store.save(sanitize(draft))
    marker.write_text("seeded\n", encoding="utf-8")


def draft_from_pdf(source, filename: str, policy_id: str | None = None, status: str = "draft") -> dict:
    policy = extract_policy(source, filename, policy_id)
    roles = [{"role": role, "responsibility": duty} for role, duty in read_role_rows(source)]
    sections = []
    for top in policy.sections:
        if "." in top.id:
            continue
        children = [item for item in policy.sections if item.id.startswith(f"{top.id}.")]
        if roles and "role" in top.heading.lower():
            sections.append(_section(top.heading, "", [_sub("", "roles", rows=roles)]))
            continue
        subsections = []
        for child in children:
            if policy.entitlements and (child.id.endswith(".0") or "entitlement" in child.heading.lower()):
                subsections.append(
                    _sub(
                        "Summary of Entitlements",
                        "entitlements",
                        rows=[
                            {
                                "leave_type": row.leave_type,
                                "entitlement": row.entitlement,
                                "paid": row.paid,
                                "section": row.section,
                            }
                            for row in policy.entitlements
                        ],
                    )
                )
                continue
            heading = "" if child.heading.strip() == top.heading.strip() else child.heading
            body, clauses = _split_clauses(_CLOSING.sub("", child.text).strip())
            subsections.append(_sub(heading, "text", body, clauses))
        sections.append(_section(top.heading, _CLOSING.sub("", top.text).strip(), subsections))
    if not sections:
        sections = [_section("Purpose", policy.prompt_text()[:4000])]
    return {
        "id": policy.id,
        "title": policy.title,
        "disclaimer": _disclaimer(policy.intro, policy.title),
        "status": "published" if status == "published" else "draft",
        "metadata": {key: policy.metadata.get(key, "") for key in (
            "Policy number",
            "Version",
            "Effective date",
            "Policy owner",
            "Applies to",
        )},
        "sections": sections,
    }


def _disclaimer(intro: str, title: str) -> str:
    kept = []
    for line in intro.splitlines():
        text = line.strip()
        if not text or text == title or META_RE.match(text):
            continue
        kept.append(text)
    return " ".join(kept)


def _split_clauses(text: str) -> tuple[str, list[str]]:
    flat = re.sub(r"\s+", " ", text).strip()
    matches = [match for match in _CLAUSE.finditer(flat)]
    sequence = []
    expected = "a"
    for match in matches:
        if match.group(1) != expected:
            break
        sequence.append(match)
        expected = chr(ord(expected) + 1)
    if not sequence:
        return flat, []
    body = flat[: sequence[0].start()].strip()
    clauses = []
    for index, match in enumerate(sequence):
        end = sequence[index + 1].start() if index + 1 < len(sequence) else len(flat)
        clauses.append(flat[match.end() : end].strip())
    return body, clauses
