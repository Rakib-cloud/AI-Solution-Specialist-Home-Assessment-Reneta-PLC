from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.services.models import Entitlement, PolicyDocument, Section

_ID = re.compile(r"^[a-f0-9]{32}$")
_META_KEYS = ("Policy number", "Version", "Effective date", "Policy owner", "Applies to")
SAMPLE_POLICY_ID = "c4e1a9e0000000000000000000000004"


def blank_policy() -> dict:
    return {
        "title": "",
        "disclaimer": "",
        "status": "draft",
        "metadata": {key: "" for key in _META_KEYS},
        "sections": [_section("Purpose")],
    }


def sample_outline() -> dict:
    leave_names = [
        "Annual Leave",
        "Casual Leave",
        "Sick Leave",
        "Maternity Leave",
        "Paternity Leave",
        "Marriage Leave",
        "Bereavement Leave",
        "Compensatory Off",
    ]
    draft = {
        "title": "",
        "disclaimer": (
            "This policy sets out the types of leave available to employees, how leave is earned "
            "and used, and how it is requested and approved."
        ),
        "status": "draft",
        "metadata": {
            "Policy number": "",
            "Version": "1.0",
            "Effective date": "",
            "Policy owner": "Human Resources Department",
            "Applies to": "All permanent full-time employees",
        },
        "sections": [
            _section("Purpose"),
            _section("Scope and Eligibility", subsections=[_sub(), _sub(), _sub()]),
            _section("Leave Year"),
            _section(
                "Types of Leave",
                subsections=[
                    _sub(
                        "Summary of Entitlements",
                        kind="entitlements",
                        rows=[
                            {"leave_type": name, "entitlement": "", "paid": "Yes", "section": ""}
                            for name in leave_names
                        ],
                    ),
                    _sub("Annual Leave", clauses=[""]),
                    _sub("Casual Leave", clauses=[""]),
                    _sub("Sick Leave", clauses=[""]),
                    _sub("Maternity Leave", clauses=[""]),
                    _sub("Paternity Leave", clauses=[""]),
                    _sub("Marriage Leave", clauses=[""]),
                    _sub("Bereavement Leave", clauses=[""]),
                    _sub("Compensatory Off", clauses=[""]),
                ],
            ),
            _section("Weekly Holidays and Public Holidays", subsections=[_sub(), _sub(), _sub()]),
            _section("Applying for Leave", subsections=[_sub(), _sub(), _sub(), _sub()]),
            _section("Leave During Notice Period"),
            _section(
                "Leave Without Pay and Unauthorised Absence",
                subsections=[_sub(), _sub(), _sub()],
            ),
            _section("Confidentiality of Leave Records", subsections=[_sub(), _sub(), _sub()]),
            _section(
                "Roles and Responsibilities",
                subsections=[
                    _sub(
                        "",
                        kind="roles",
                        rows=[
                            {"role": "Employee", "responsibility": ""},
                            {"role": "Line manager", "responsibility": ""},
                            {"role": "HR Department", "responsibility": ""},
                        ],
                    )
                ],
            ),
            _section("Policy Review and Contact", subsections=[_sub(), _sub()]),
        ],
    }
    return draft


def template_draft() -> dict:
    from app.services.importer import sample_draft

    return sample_draft() or sample_outline()


def template_defaults() -> dict:
    """The few facts a new leave policy has to supply, taken from the sample."""
    draft = template_draft()
    rows = []
    for _index, table in _entitlement_tables(draft):
        rows = [
            {
                "leave_type": row.get("leave_type", ""),
                "entitlement": row.get("entitlement", ""),
                "paid": row.get("paid", "Yes"),
            }
            for row in table.get("rows") or []
        ]
        break
    return {
        "title": draft.get("title", ""),
        "metadata": draft.get("metadata", {}),
        "entitlements": rows,
        "outline": [section.get("heading", "") for section in draft.get("sections") or []],
    }


def new_policy(
    kind: str = "blank",
    title: str | None = None,
    metadata: dict | None = None,
    entitlements: list | None = None,
) -> dict:
    draft = template_draft() if kind == "sample" else blank_policy()
    draft["id"] = uuid.uuid4().hex
    draft["status"] = "draft"
    if title:
        if kind == "sample":
            _adopt_company(draft, title)
        draft["title"] = title
    if metadata:
        current = draft.get("metadata") or {}
        for key in _META_KEYS:
            if metadata.get(key) is not None:
                current[key] = metadata[key]
        draft["metadata"] = current
    if entitlements is not None:
        apply_entitlements(draft, entitlements)
    draft["updated_at"] = _now()
    return sanitize(draft)


def _adopt_company(draft: dict, title: str) -> None:
    """Put the new policy's company into the template in place of the sample's.

    The sample names a fictitious company in its opening note and in several
    sentences. A policy written from the template belongs to someone else.
    """
    draft["disclaimer"] = sample_outline()["disclaimer"]
    old = _company(draft.get("title"))
    new = _company(title)
    if not old or not new or old == new:
        return
    for section in draft.get("sections") or []:
        section["body"] = section.get("body", "").replace(old, new)
        for child in section.get("subsections") or []:
            child["body"] = child.get("body", "").replace(old, new)
            child["clauses"] = [clause.replace(old, new) for clause in child.get("clauses") or []]
            for row in child.get("rows") or []:
                for key, value in list(row.items()):
                    if isinstance(value, str):
                        row[key] = value.replace(old, new)


def _company(title) -> str:
    """"Northwind Leave Policy" -> "Northwind"."""
    return re.sub(r"\s*(annual\s+)?leave\s+policy\s*$", "", str(title or ""), flags=re.I).strip()


def apply_entitlements(draft: dict, rows: list) -> None:
    """Rewrite the entitlements table and keep one subsection per leave type.

    The sample numbers that table 4.0 and each leave type 4.1, 4.2, and so on, so
    removing a leave type here also removes its subsection and renumbers the rest.
    """
    for index, table in _entitlement_tables(draft):
        section = draft["sections"][index - 1]
        children = section.get("subsections") or []
        by_name = {}
        for child in children[1:]:
            by_name.setdefault(_name_key(child.get("heading")), child)
        detail: list[dict] = []
        table_rows: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            leave_type = _clip(row.get("leave_type"), 120)
            if not leave_type:
                continue
            child = by_name.pop(_name_key(leave_type), None) or _sub(leave_type, clauses=[""])
            child["heading"] = leave_type
            detail.append(child)
            table_rows.append(
                {
                    "leave_type": leave_type,
                    "entitlement": _clip(row.get("entitlement"), 160),
                    "paid": _clip(row.get("paid"), 40) or "Yes",
                    "section": f"{index}.{len(detail)}",
                }
            )
        if not table_rows:
            return
        table["rows"] = table_rows
        section["subsections"] = [table] + detail
        return


def _entitlement_tables(draft: dict):
    for index, section in enumerate(draft.get("sections") or [], start=1):
        children = section.get("subsections") or []
        if children and children[0].get("kind") == "entitlements":
            yield index, children[0]


def _name_key(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def sanitize(raw: dict) -> dict:
    sections = []
    for section in (raw.get("sections") or [])[:40]:
        if not isinstance(section, dict):
            continue
        children = []
        for child in (section.get("subsections") or [])[:30]:
            if not isinstance(child, dict):
                continue
            kind = child.get("kind") if child.get("kind") in {"text", "entitlements", "roles"} else "text"
            children.append(
                {
                    "heading": _clip(child.get("heading"), 120),
                    "kind": kind,
                    "body": _clip(child.get("body"), 4000),
                    "clauses": [_clip(item, 2000) for item in (child.get("clauses") or [])[:20] if _clip(item, 2000)],
                    "rows": _rows(kind, child.get("rows")),
                }
            )
        sections.append(
            {
                "heading": _clip(section.get("heading"), 120) or "Untitled section",
                "body": _clip(section.get("body"), 4000),
                "subsections": children,
            }
        )
    if not sections:
        sections = [_section("Purpose")]
    metadata = {}
    incoming = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    for key in _META_KEYS:
        metadata[key] = _clip(incoming.get(key), 160)
    status = "published" if raw.get("status") == "published" else "draft"
    return {
        "id": raw.get("id") if _ID.match(str(raw.get("id") or "")) else uuid.uuid4().hex,
        "title": _clip(raw.get("title"), 160),
        "disclaimer": _clip(raw.get("disclaimer"), 600),
        "status": status,
        "metadata": metadata,
        "sections": sections,
        "updated_at": raw.get("updated_at") or _now(),
    }


def validate_for_publish(draft: dict) -> list[str]:
    errors = []
    if not draft.get("title", "").strip():
        errors.append("Add a policy title before publishing.")
    if not _has_content(draft):
        errors.append("Add section text, a clause, or a table row before publishing.")
    return errors


def to_policy_document(draft: dict, page_count: int = 1) -> PolicyDocument:
    sections: list[Section] = []
    entitlements: list[Entitlement] = []
    for number, section, children in _numbered(draft):
        body = section.get("body", "").strip()
        kept = []
        for child_id, child in children:
            if child.get("kind") == "roles" and not (child.get("heading") or "").strip() and not body:
                body = _child_text(child)
                continue
            kept.append((child_id, child))
        sections.append(Section(id=number, heading=section["heading"], text=body))
        for child_id, child in kept:
            sections.append(Section(id=child_id, heading=child["heading"] or section["heading"], text=_child_text(child)))
            if child["kind"] == "entitlements":
                for row in child["rows"]:
                    if not row["leave_type"] or not row["entitlement"]:
                        continue
                    entitlements.append(
                        Entitlement(
                            leave_type=row["leave_type"],
                            entitlement=row["entitlement"],
                            paid=row.get("paid", ""),
                            section=row.get("section") or "",
                        )
                    )
    title = draft.get("title") or "Leave policy"
    filename = _pdf_name(title)
    return PolicyDocument(
        id=draft["id"],
        filename=filename,
        page_count=page_count,
        title=title,
        metadata={key: value for key, value in draft.get("metadata", {}).items() if value},
        intro=draft.get("disclaimer", ""),
        sections=sections,
        entitlements=entitlements,
    )


def summary(draft: dict) -> dict:
    return {
        "id": draft["id"],
        "title": draft.get("title") or "Untitled policy",
        "status": draft.get("status", "draft"),
        "updated_at": draft.get("updated_at"),
        "policy_number": (draft.get("metadata") or {}).get("Policy number", ""),
        "version": (draft.get("metadata") or {}).get("Version", ""),
    }


class DraftStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root) / "authored"
        self.root.mkdir(parents=True, exist_ok=True)

    def list_all(self) -> list[dict]:
        drafts = []
        for path in self.root.glob("*.json"):
            if not _ID.match(path.stem):
                continue
            drafts.append(summary(json.loads(path.read_text(encoding="utf-8"))))
        drafts.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return drafts

    def load(self, policy_id: str) -> dict | None:
        path = self._path(policy_id)
        if path is None or not path.is_file():
            return None
        return sanitize(json.loads(path.read_text(encoding="utf-8")))

    def save(self, draft: dict) -> dict:
        clean = sanitize(draft)
        clean["updated_at"] = _now()
        self._path(clean["id"]).write_text(json.dumps(clean, indent=2), encoding="utf-8")
        return clean

    def delete(self, policy_id: str) -> bool:
        path = self._path(policy_id)
        if path is None or not path.is_file():
            return False
        path.unlink()
        return True

    def _path(self, policy_id: str) -> Path | None:
        if not _ID.match(policy_id or ""):
            return None
        return self.root / f"{policy_id}.json"


def _numbered(draft: dict):
    for index, section in enumerate(draft.get("sections") or [], start=1):
        number = str(index)
        children = section.get("subsections") or []
        start = 0 if children and children[0].get("kind") == "entitlements" else 1
        numbered = [(f"{number}.{start + offset}", child) for offset, child in enumerate(children)]
        yield number, section, numbered


def _child_text(child: dict) -> str:
    parts: list[str] = []
    if child.get("body"):
        parts.append(child["body"].strip())
    for index, clause in enumerate(child.get("clauses") or []):
        if clause.strip():
            parts.append(f"({chr(ord('a') + index)}) {clause.strip()}")
    if child.get("kind") == "entitlements":
        lines = ["Leave type | Entitlement | Paid | Section"]
        for row in child.get("rows") or []:
            if not row.get("leave_type"):
                continue
            lines.append(
                f"{row.get('leave_type', '')} | {row.get('entitlement', '')} | "
                f"{row.get('paid', '')} | {row.get('section', '')}"
            )
        if len(lines) > 1:
            parts.append("\n".join(lines))
    if child.get("kind") == "roles":
        lines = ["Role | Responsibility"]
        for row in child.get("rows") or []:
            if not row.get("role"):
                continue
            lines.append(f"{row.get('role', '')} | {row.get('responsibility', '')}")
        if len(lines) > 1:
            parts.append("\n".join(lines))
    return "\n".join(parts).strip()


def _has_content(draft: dict) -> bool:
    for section in draft.get("sections") or []:
        if section.get("body", "").strip():
            return True
        for child in section.get("subsections") or []:
            if child.get("body", "").strip() or any(item.strip() for item in child.get("clauses") or []):
                return True
            for row in child.get("rows") or []:
                if child.get("kind") == "roles" and str(row.get("responsibility") or "").strip():
                    return True
                if child.get("kind") == "entitlements" and str(row.get("entitlement") or "").strip():
                    return True
    return False


def _rows(kind: str, rows) -> list[dict]:
    cleaned = []
    for row in (rows or [])[:24]:
        if not isinstance(row, dict):
            continue
        if kind == "entitlements":
            cleaned.append(
                {
                    "leave_type": _clip(row.get("leave_type"), 80),
                    "entitlement": _clip(row.get("entitlement"), 160),
                    "paid": _clip(row.get("paid"), 20),
                    "section": _clip(row.get("section"), 20),
                }
            )
        elif kind == "roles":
            cleaned.append(
                {
                    "role": _clip(row.get("role"), 80),
                    "responsibility": _clip(row.get("responsibility"), 400),
                }
            )
    return [row for row in cleaned if any(row.values())]


def _section(heading: str, body: str = "", subsections: list | None = None) -> dict:
    return {"heading": heading, "body": body, "subsections": subsections or []}


def _sub(heading: str = "", kind: str = "text", body: str = "", clauses: list | None = None, rows: list | None = None) -> dict:
    return {"heading": heading, "kind": kind, "body": body, "clauses": clauses or [], "rows": rows or []}


def _clip(value, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _pdf_name(title: str) -> str:
    stem = re.sub(r"[^\w.\- ()]", "", title).strip() or "leave-policy"
    return f"{stem}.pdf"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
