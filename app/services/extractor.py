from __future__ import annotations

import re
import uuid
from io import BytesIO
from pathlib import Path

import pdfplumber

from app.services.models import Entitlement, PolicyDocument, Section, squash

SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
PAGE_RE = re.compile(r"^Page \d+ of \d+$")
META_RE = re.compile(r"^(Policy number|Version|Effective date|Policy owner|Applies to)\s+(.+)$")
HEADER = "XYZ Company Leave Policy (Sample)"


def extract_policy(source: str | Path | bytes, filename: str, policy_id: str | None = None) -> PolicyDocument:
    pages: list[str] = []
    metadata: dict[str, str] = {}
    entitlements: list[Entitlement] = []
    role_rows: list[tuple[str, str]] = []

    with _open_pdf(source) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
            for table in page.extract_tables() or []:
                meta = _metadata_from_table(table)
                metadata.update(meta)
                found = _entitlements_from_table(table)
                if found:
                    entitlements = found
                roles = _roles_from_table(table)
                if roles:
                    role_rows = roles

    lines = _clean_lines("\n".join(pages))
    intro, sections = _parse_sections(lines)
    metadata.update(_metadata_from_lines(intro))
    _attach_roles(sections, role_rows)
    _attach_entitlements(sections, entitlements)
    title = _title_from(intro, filename)
    return PolicyDocument(
        id=policy_id or uuid.uuid4().hex,
        filename=filename,
        page_count=page_count,
        title=title,
        metadata=metadata,
        intro="\n".join(intro),
        sections=sections,
        entitlements=entitlements,
    )


def _open_pdf(source: str | Path | bytes):
    if isinstance(source, (bytes, bytearray)):
        return pdfplumber.open(BytesIO(source))
    return pdfplumber.open(Path(source))


def read_role_rows(source: str | Path | bytes) -> list[tuple[str, str]]:
    roles: list[tuple[str, str]] = []
    with _open_pdf(source) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                found = _roles_from_table(table)
                if found:
                    roles = found
    return roles


def _clean_lines(text: str) -> list[str]:
    text = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\xa0", " ")
    )
    lines: list[str] = []
    for raw in text.splitlines():
        line = squash(raw)
        if not line or line == HEADER or PAGE_RE.match(line):
            continue
        lines.append(line)
    return lines


def _parse_sections(lines: list[str]) -> tuple[list[str], list[Section]]:
    intro: list[str] = []
    sections: list[Section] = []
    headings: dict[str, str] = {}
    current: Section | None = None

    for line in lines:
        match = SECTION_RE.match(line)
        if match and _is_real_section(match.group(1), match.group(2)):
            section_id, rest = match.group(1), match.group(2).strip()
            if _is_heading(rest):
                headings[section_id] = rest
                current = Section(id=section_id, heading=rest, text="")
            else:
                parent = _parent_heading(section_id, headings)
                current = Section(id=section_id, heading=parent, text=rest)
            sections.append(current)
            continue
        if current is None:
            intro.append(line)
        else:
            current.text = _join(current.text, line)
    return intro, sections


def _is_real_section(section_id: str, rest: str) -> bool:
    major = int(section_id.split(".")[0])
    if major < 1 or major > 40:
        return False
    if re.fullmatch(r"\d{4}", rest.split()[0] if rest else ""):
        return False
    return True


def _is_heading(rest: str) -> bool:
    words = rest.split()
    if not words or len(words) > 8 or rest.endswith("."):
        return False
    return True


def _parent_heading(section_id: str, headings: dict[str, str]) -> str:
    if "." not in section_id:
        return "Policy"
    parent = section_id.rsplit(".", 1)[0]
    return headings.get(parent, "Policy")


def _join(existing: str, line: str) -> str:
    if not existing:
        return line
    if existing.endswith("-") and len(existing) > 1 and existing[-2].isalpha():
        return existing[:-1] + line
    if line.startswith("("):
        return existing + "\n" + line
    return existing + " " + line


def _metadata_from_lines(lines: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines:
        match = META_RE.match(line)
        if match:
            found[match.group(1)] = match.group(2).strip()
    return found


def _metadata_from_table(table: list[list[str | None]]) -> dict[str, str]:
    found: dict[str, str] = {}
    for row in table:
        cells = [_cell(cell) for cell in row]
        if len(cells) >= 2 and cells[0] in {"Policy number", "Version", "Effective date", "Policy owner", "Applies to"}:
            found[cells[0]] = cells[1]
    return found


def _entitlements_from_table(table: list[list[str | None]]) -> list[Entitlement]:
    rows = [[_cell(cell) for cell in row] for row in table]
    header_index = None
    for index, row in enumerate(rows):
        lowered = [cell.lower() for cell in row]
        if "leave type" in lowered and "entitlement" in lowered:
            header_index = index
            break
    if header_index is None:
        return []
    header = [cell.lower() for cell in rows[header_index]]
    type_at = header.index("leave type")
    entitlement_at = header.index("entitlement")
    paid_at = header.index("paid") if "paid" in header else None
    section_at = header.index("section") if "section" in header else None
    entitlements: list[Entitlement] = []
    for row in rows[header_index + 1 :]:
        if len(row) <= type_at or not row[type_at]:
            continue
        entitlements.append(
            Entitlement(
                leave_type=row[type_at],
                entitlement=row[entitlement_at] if len(row) > entitlement_at else "",
                paid=row[paid_at] if paid_at is not None and len(row) > paid_at else "",
                section=row[section_at] if section_at is not None and len(row) > section_at else "",
            )
        )
    return entitlements


def _roles_from_table(table: list[list[str | None]]) -> list[tuple[str, str]]:
    rows = [[_cell(cell) for cell in row] for row in table]
    if not rows:
        return []
    header = [cell.lower() for cell in rows[0]]
    if "role" not in header or "responsibility" not in header:
        return []
    role_at = header.index("role")
    duty_at = header.index("responsibility")
    roles: list[tuple[str, str]] = []
    for row in rows[1:]:
        if len(row) <= max(role_at, duty_at) or not row[role_at]:
            continue
        roles.append((row[role_at], row[duty_at]))
    return roles


def _attach_roles(sections: list[Section], roles: list[tuple[str, str]]) -> None:
    if not roles:
        return
    section = next((item for item in sections if item.id == "10"), None)
    if section is None:
        return
    if roles[0][1] and roles[0][1].split()[0].lower() in section.text.lower():
        return
    lines = ["Role | Responsibility"]
    lines.extend(f"{role} | {duty}" for role, duty in roles)
    section.text = _join(section.text, "\n".join(lines))


def _attach_entitlements(sections: list[Section], entitlements: list[Entitlement]) -> None:
    if not entitlements:
        return
    section = next((item for item in sections if item.id == "4.0"), None)
    if section is None:
        return
    if entitlements[0].entitlement.lower() in section.text.lower():
        return
    lines = ["Leave type | Entitlement | Paid | Section"]
    lines.extend(
        f"{row.leave_type} | {row.entitlement} | {row.paid} | {row.section}" for row in entitlements
    )
    section.text = _join(section.text, "\n".join(lines))


def _title_from(intro: list[str], filename: str) -> str:
    for line in intro:
        if line.lower().startswith("sample document"):
            continue
        if META_RE.match(line):
            continue
        return line
    return Path(filename).stem


def _cell(value: str | None) -> str:
    return squash((value or "").replace("\n", " "))
