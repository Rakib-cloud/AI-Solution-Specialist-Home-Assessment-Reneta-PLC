from __future__ import annotations

import re

from app.services.grounded import valid_citations
from app.services.models import PolicyDocument, Section, squash

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at", "by", "with",
    "from", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "can", "could", "should", "would", "may", "might", "will", "shall", "i", "me",
    "my", "we", "our", "you", "your", "it", "this", "that", "these", "those", "what",
    "when", "where", "which", "who", "whom", "how", "many", "much", "if", "about",
    "into", "over", "under", "than", "then", "there", "their", "them", "as", "not",
    "no", "yes", "please", "tell", "give", "need", "needed", "per", "any", "all",
    "during", "after", "before", "while", "also", "only", "just", "have", "has", "had",
    "get", "gets", "got", "am", "im", "there", "here",
    # question scaffolding that matches almost any sentence
    "happen", "happens", "long", "still", "mean", "means", "told", "say", "says",
}
_GENERIC = {
    "leave", "day", "days", "employee", "employees", "policy", "company", "paid",
    "work", "working", "time", "year", "years", "annually", "yearly",
}
# a definition question wants the sentence that introduces the thing
_DEFINITION = re.compile(r"^\s*(what('s| is| are)|define|explain)\b", re.I)
# "(see Section 8)" points somewhere else; it is never the answer
_CROSS_REF = re.compile(r"\(\s*see[^)]*\)", re.I)
_ALIASES = {
    "father": ("parent",),
    "mother": ("parent",),
    "dad": ("parent",),
    "mum": ("parent",),
    "wife": ("spouse",),
    "husband": ("spouse",),
    "son": ("child",),
    "daughter": ("child",),
    "brother": ("sibling",),
    "sister": ("sibling",),
    "dies": ("death",),
    "died": ("death",),
    "dead": ("death",),
    "email": ("contact",),
    "mail": ("contact",),
    "weekend": ("friday", "saturday", "weekly"),
    "encash": ("encashed",),
    "encashed": ("encash",),
    "certificate": ("medical",),
    "probation": ("confirmation",),
    "intern": ("interns",),
    "interns": ("intern",),
    "refuse": ("refused",),
    "approve": ("approval", "approved"),
    "holiday": ("holidays",),
    "holidays": ("holiday",),
    "carry": ("carried",),
    "record": ("records",),
    "records": ("record",),
    "access": ("accessed",),
    "confidential": ("confidentiality",),
    "friday": ("weekly",),
    "saturday": ("weekly",),
    "apply": ("request", "requested", "submit", "peoplehub", "portal"),
    "applying": ("request", "requested", "submit", "peoplehub", "portal"),
    "see": ("accessed", "access"),
    "view": ("accessed", "access"),
    "start": ("runs", "begins"),
    "starts": ("runs", "begins"),
    "end": ("runs", "december"),
    "ends": ("runs", "december"),
    "absent": ("absence",),
    "absence": ("absent",),
    "notice": ("advance", "notify", "notification", "inform"),
    "accrual": ("accrues", "accrue"),
    "accrue": ("accrues",),
    "respond": ("acted", "act"),
    "resign": ("separation",),
    "resigning": ("separation",),
    "resignation": ("separation",),
    "quit": ("separation",),
    "response": ("acted", "act"),
}


def read_answer(question: str, policy: PolicyDocument) -> tuple[str, list[str]] | None:
    query = _query_items(question)
    if not query:
        return None
    wants_email = bool(re.search(r"\b(e-?mail|mail address)\b", question, re.I))
    defines = bool(_DEFINITION.match(question))
    named = _named_leave_type(question, policy)
    best: tuple[float, Section, list[tuple[float, int, str]]] | None = None
    for section in policy.sections:
        if not section.text.strip():
            continue
        # a question that names one leave type is answered by passages about it
        if named and named not in f"{section.heading} {section.text}".lower():
            continue
        heading = _stems(section.heading)
        # the question naming the section's topic is strong evidence on its own
        on_topic = _heading_phrase(section.heading, question)
        ranked: list[tuple[float, int, str]] = []
        for index, sentence in enumerate(section.sentences()):
            score, specific = _score(query, _stems(_CROSS_REF.sub(" ", sentence)), heading)
            if on_topic:
                score += 0.8
                specific = True
            if wants_email and "@" in sentence:
                score += 1.5
                specific = True
            if defines and index == 0:
                score += 1.2
            if specific and score >= 1:
                ranked.append((score, index, sentence))
        if not ranked:
            continue
        ranked.sort(key=lambda item: (-item[0], item[1]))
        top = ranked[0][0]
        if best is None or top > best[0]:
            best = (top, section, ranked)
    if best is None or best[0] < 1:
        return None
    _, section, ranked = best
    top = ranked[0][0]
    chosen = [item for item in ranked if item[0] >= top * 0.75][:2]
    chosen.sort(key=lambda item: item[1])
    answer = " ".join(squash(item[2]) for item in chosen)
    return answer, valid_citations([section.id], policy)


def _named_leave_type(question: str, policy: PolicyDocument) -> str:
    """The one leave type the question is about, taken from the policy's own table."""
    asked = question.lower()
    found = {row.leave_type.lower() for row in policy.entitlements if row.leave_type.lower() in asked}
    return next(iter(found)) if len(found) == 1 else ""


def topic_is_absent(question: str, policy: PolicyDocument) -> bool:
    """True when what the question is about never appears in the policy.

    The last meaningful word of a question carries its subject: "leave for jury
    duty", "the annual salary increment". If that word and its aliases are
    nowhere in the policy, the policy does not cover the question, however many
    common words the two happen to share.
    """
    items = _query_items(question)
    focus = next((token for token, _weight, specific in reversed(items) if specific and len(token) >= 4), "")
    if not focus:
        return False
    known = _policy_stems(policy)
    if focus in known:
        return False
    for word, aliases in _ALIASES.items():
        if _stem(word) != focus:
            continue
        if any(_stem(alias) in known for alias in aliases):
            return False
    return True


_STEM_CACHE: dict[str, set[str]] = {}


def _policy_stems(policy: PolicyDocument) -> set[str]:
    cached = _STEM_CACHE.get(policy.id)
    if cached is None:
        cached = _stems(policy.text_lower)
        _STEM_CACHE[policy.id] = cached
    return cached


def _heading_phrase(heading: str, question: str) -> bool:
    words = [word for word in re.findall(r"[a-z0-9]+", (heading or "").lower()) if word not in _STOP]
    if len(words) < 2:
        return False
    return " ".join(words) in " ".join(re.findall(r"[a-z0-9]+", question.lower()))


def document_quotes(policy: PolicyDocument, limit: int = 6) -> list[dict]:
    ranked: list[tuple[int, str, str, str]] = []
    for section in policy.sections:
        for sentence in section.sentences():
            text = squash(sentence)
            if len(text) < 40:
                continue
            lowered = text.lower()
            score = 0
            if "applies to" in lowered:
                score += 6
            if "not covered" in lowered:
                score += 5
            if "confidential" in lowered:
                score += 5
            if re.search(r"\d", text):
                score += 2
            if "must" in lowered or "may not" in lowered:
                score += 2
            if score:
                ranked.append((score, section.id, section.heading, text))
    ranked.sort(key=lambda item: item[0], reverse=True)
    quotes = []
    seen: set[str] = set()
    for _, section_id, heading, text in ranked:
        if section_id in seen:
            continue
        seen.add(section_id)
        quotes.append({"section": section_id, "heading": heading, "quote": text})
        if len(quotes) == limit:
            break
    return quotes


def _query_items(question: str) -> list[tuple[str, float, bool]]:
    items: list[tuple[str, float, bool]] = []
    seen: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", question.lower()):
        if word in _STOP:
            continue
        token = _stem(word)
        specific = token not in _GENERIC and word not in _GENERIC
        # figures are the most telling part of a leave question: 3 days, 10 days, 30
        number = word.isdigit()
        if (len(token) >= 2 or number) and token not in seen:
            seen.add(token)
            items.append((token, 1.4 if number else 1.0, specific))
        for alias in _ALIASES.get(word, ()):
            alias_token = _stem(alias)
            if len(alias_token) >= 3 and alias_token not in seen:
                seen.add(alias_token)
                items.append((alias_token, 0.85, specific))
    return items


def _score(query: list[tuple[str, float, bool]], sentence: set[str], heading: set[str]) -> tuple[float, bool]:
    score = 0.0
    specific = False
    for token, weight, is_specific in query:
        if token not in sentence and token not in heading:
            continue
        if token in sentence:
            score += weight
        elif token in heading:
            score += weight * 0.7
        if is_specific:
            specific = True
    if sentence:
        score += min(score, 3) / max(len(sentence), 1)
    return score, specific


def _stems(text: str) -> set[str]:
    found: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        found.add(word)
        found.add(_stem(word))
    return found


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 5 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word
