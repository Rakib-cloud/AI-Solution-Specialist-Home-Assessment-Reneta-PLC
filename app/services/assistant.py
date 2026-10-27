from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.grounded import (
    UNKNOWN_MESSAGE,
    asks_for_other_personal_data,
    is_hard_unknown,
    numbers_are_grounded,
    privacy_message,
    reconcile_answer,
    source_line,
    valid_citations,
)
from app.services.models import PolicyDocument, squash
from app.services.reader import document_quotes, read_answer, topic_is_absent

ANSWER_SYSTEM = """You are an HR leave-policy assistant. You answer only from the policy text in the user message. You do not use labour law, common company practice, or outside knowledge.

Return a JSON object with this shape:
{"status": "answer" | "unknown" | "privacy", "answer": "plain sentences", "citations": ["4.2"]}

Rules:
- Use status "answer" only when the policy text states the fact the user asked for. Put the section id of every passage you used in citations. Section ids must come from the section index. Do not invent section numbers.
- Do not add rules, numbers, durations, eligibility, or exceptions that the policy does not state. Keep working days and calendar days exactly as written. Figures that appear only in the entitlements table are valid.
- If the policy explicitly excludes a group, or limits a rule to one leave type, that is an answer. Cite that section. Do not call it unknown.
- Use status "unknown" when the policy does not state the answer. Leave citations empty and leave answer as an empty string. Do not guess.
- Use status "privacy" only when the user asks for another employee's personal leave record, balance, days taken, medical information, or reason for absence. Questions about what the policy itself says about confidentiality are normal questions. Answer those from the policy.
- A question about the user's own used or remaining balance is unknown. This policy has no personal records.
- Do not apply a rule written for one leave type to a different leave type.
- Write the answer as plain sentences. No markdown. No source line. At most five sentences.
"""

ANALYSIS_SYSTEM = """You review an uploaded leave policy. Return JSON:
{"quotes": [{"section": "2.1", "quote": "exact sentence copied from that section"}]}

Choose up to 6 short sentences that state eligibility, entitlements, exclusions, or confidentiality.
Copy each quote exactly from the policy text. Do not paraphrase. Do not add rules.
"""


@dataclass
class AnswerResult:
    kind: str
    text: str
    citations: list[dict] = field(default_factory=list)


class _Retry(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def answer_question(question: str, policy: PolicyDocument, llm=None) -> AnswerResult:
    question = question.strip()
    if asks_for_other_personal_data(question):
        return _privacy_result(policy)
    if is_hard_unknown(question, policy) or topic_is_absent(question, policy):
        return AnswerResult("unknown", UNKNOWN_MESSAGE, [])
    grounded = _answer_from_document(question, policy)
    if grounded is not None:
        return grounded
    found = read_answer(question, policy)
    if found is not None:
        answer, citations = found
        answer = _clean_answer(answer)
        citations = valid_citations(citations, policy)
        if answer and citations and numbers_are_grounded(answer, policy):
            text = answer + "\n\n" + source_line(policy, citations)
            return AnswerResult("answer", text, _citation_payload(policy, citations))
    return AnswerResult("unknown", UNKNOWN_MESSAGE, [])


def analyze_policy(policy: PolicyDocument, llm=None) -> list[dict]:
    return document_quotes(policy)


def _finalize(raw: dict, question: str, policy: PolicyDocument) -> AnswerResult:
    status = str(raw.get("status") or "").strip().lower()
    answer = _clean_answer(str(raw.get("answer") or ""))
    citations = valid_citations(_citation_ids(raw.get("citations")), policy)

    if status == "privacy":
        raise _Retry(
            "This question is about the policy text, not a request for another employee's personal record. "
            "Answer from the policy, or use status unknown if the policy does not state it."
        )

    fixed = reconcile_answer(question, answer if status == "answer" else "", citations, policy)
    if fixed is not None:
        answer, raw_ids = fixed
        answer = _clean_answer(answer)
        citations = valid_citations(raw_ids, policy)
        status = "answer"

    if status == "unknown" or re.match(r"i don't know\b", answer, re.I):
        return AnswerResult("unknown", UNKNOWN_MESSAGE, [])
    if status != "answer":
        raise _Retry('status must be "answer" or "unknown".')
    if not answer:
        raise _Retry("answer is empty.")
    if not citations:
        raise _Retry("citations must list at least one section id that exists in the section index.")
    if not numbers_are_grounded(answer, policy):
        raise _Retry("the answer contains a number that is not written in the policy. Remove it.")

    text = answer + "\n\n" + source_line(policy, citations)
    return AnswerResult("answer", text, _citation_payload(policy, citations))


def _answer_from_document(question: str, policy: PolicyDocument) -> AnswerResult | None:
    fixed = reconcile_answer(question, "", [], policy)
    if fixed is None:
        return None
    answer, raw_ids = fixed
    answer = _clean_answer(answer)
    citations = valid_citations(raw_ids, policy)
    if not answer or not citations or not numbers_are_grounded(answer, policy):
        return None
    return AnswerResult("answer", answer + "\n\n" + source_line(policy, citations), _citation_payload(policy, citations))


def _question_prompt(policy: PolicyDocument, question: str) -> str:
    index = "\n".join(f"{section.id} {section.heading}" for section in policy.sections)
    return f"SECTION INDEX\n{index}\n\nPOLICY\n{policy.prompt_text()}\n\nQUESTION\n{question}"


def _citation_ids(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            ids.append(str(item.get("section") or item.get("id") or ""))
    return ids


def _citation_payload(policy: PolicyDocument, ids: list[str]) -> list[dict]:
    payload = []
    for section_id in ids:
        section = policy.section(section_id)
        if section is not None:
            payload.append({"id": section.id, "heading": section.heading})
    return payload


def _privacy_result(policy: PolicyDocument) -> AnswerResult:
    return AnswerResult("privacy", privacy_message(policy), _citation_payload(policy, _privacy_ids(policy)))


def _privacy_ids(policy: PolicyDocument) -> list[str]:
    for section in policy.sections:
        if "confidential" in section.heading.lower():
            return [section.id]
    return []


def _section_containing(quote: str, policy: PolicyDocument):
    needle = squash(quote).lower()
    if len(needle) < 20:
        return None
    for section in policy.sections:
        if needle in squash(section.text).lower():
            return section
    return None


def _clean_answer(answer: str) -> str:
    text = re.sub(r"<[^>]+>", "", answer)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\n*Source:.*\Z", "", text, flags=re.S)
    return text.strip()
