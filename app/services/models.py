from __future__ import annotations

import re
from dataclasses import dataclass, field


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Entitlement:
    leave_type: str
    entitlement: str
    paid: str
    section: str

    def to_dict(self) -> dict:
        return {
            "leave_type": self.leave_type,
            "entitlement": self.entitlement,
            "paid": self.paid,
            "section": self.section,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Entitlement:
        return cls(
            leave_type=data["leave_type"],
            entitlement=data["entitlement"],
            paid=data["paid"],
            section=data["section"],
        )


@dataclass
class Section:
    id: str
    heading: str
    text: str

    def to_dict(self) -> dict:
        return {"id": self.id, "heading": self.heading, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict) -> Section:
        return cls(id=data["id"], heading=data["heading"], text=data["text"])

    def excerpt(self, limit: int = 180) -> str:
        body = squash(self.text)
        if len(body) <= limit:
            return body
        return body[: limit - 1].rstrip() + "…"

    def sentences(self) -> list[str]:
        body = squash(self.text)
        parts = re.split(r"(?<=[.])\s+", body)
        return [part.strip() for part in parts if part.strip()]


@dataclass
class PolicyDocument:
    id: str
    filename: str
    page_count: int
    title: str
    metadata: dict[str, str]
    intro: str
    sections: list[Section]
    entitlements: list[Entitlement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "page_count": self.page_count,
            "title": self.title,
            "metadata": self.metadata,
            "intro": self.intro,
            "sections": [section.to_dict() for section in self.sections],
            "entitlements": [row.to_dict() for row in self.entitlements],
        }

    @classmethod
    def from_dict(cls, data: dict) -> PolicyDocument:
        return cls(
            id=data["id"],
            filename=data["filename"],
            page_count=data["page_count"],
            title=data["title"],
            metadata=data.get("metadata", {}),
            intro=data.get("intro", ""),
            sections=[Section.from_dict(item) for item in data.get("sections", [])],
            entitlements=[Entitlement.from_dict(item) for item in data.get("entitlements", [])],
        )

    def section(self, section_id: str) -> Section | None:
        for item in self.sections:
            if item.id == section_id:
                return item
        return None

    def prompt_text(self) -> str:
        lines: list[str] = [self.title, ""]
        for key, value in self.metadata.items():
            lines.append(f"{key}: {value}")
        if self.intro:
            lines.extend(["", squash(self.intro)])
        if self.entitlements:
            lines.extend(["", "[Section 4.0 | Summary of Entitlements]", "Leave type | Entitlement | Paid | Section"])
            for row in self.entitlements:
                lines.append(f"{row.leave_type} | {row.entitlement} | {row.paid} | {row.section}")
        for section in self.sections:
            lines.extend(["", f"[Section {section.id} | {section.heading}]"])
            if section.text.strip():
                lines.append(section.text.strip())
        return "\n".join(lines).strip()

    @property
    def text_lower(self) -> str:
        return self.prompt_text().lower()
