from __future__ import annotations

import re

from app.services.models import PolicyDocument, Section

UNKNOWN_MESSAGE = "I don't know, please contact HR."

_OTHER_PERSON = re.compile(
    r"\b(colleagues?|co-workers?|coworkers?|teammates?|team-mates?|workmates?)\b"
    r"|\b(my|our|the|his|her|their)\s+(?!hr\b|human\b)(\w+\s+)?(team|department|staff)\b"
    r"|\b(another|other|some other|any other)\s+(employee|employees|person|staff)\b"
    r"|\b(someone|somebody|anyone|anybody)\s+else\b",
    re.I,
)
# "my manager's balance" is still somebody else's record
_OTHER_POSSESSIVE = re.compile(
    r"\b(manager|supervisor|boss|director|colleague|teammate|co-?worker|employee)'s\b",
    re.I,
)
_PERSONAL_FACT = re.compile(
    r"\b("
    r"balances?|taken|already taken|used|remaining|days left|"
    r"reasons?|diagnos\w*|medical information|medical details|"
    r"records?|"
    r"illness|illnesses|ill|unwell|disease|surgery|operation|hospitalis\w*|"
    r"hospitaliz\w*|treatment|medical condition|health condition|pregnan\w*|"
    r"histor(y|ies)|uses?|using|took|days off|day off|"
    r"on medical|on sick|off sick|on leave|on maternity|on paternity|"
    r"absent|absence|"
    r"why\b.{0,50}\b(leave|sick|absent|absence|off)"
    r")\b",
    re.I,
)
_RULE_QUESTION = re.compile(
    r"("
    r"what does (the |this )?policy|"
    r"who can (access|see|view|read)|who is allowed to (see|access|view)|"
    r"are leave records confidential|is .{0,40}confidential|"
    r"does the policy allow|"
    r"can (a manager|managers|hr|the line manager) disclose|"
    r"am i allowed to request another|"
    r"can employees request another|"
    r"what does the policy say about (confidential|disclos|access)"
    r")",
    re.I,
)
_STOP_NAMES = {
    "annual", "casual", "sick", "maternity", "paternity", "marriage",
    "bereavement", "compensatory", "leave", "leaves", "policy", "company",
    "section", "employee", "employees", "manager", "managers", "department",
    "head", "intern", "interns", "consultant", "consultants", "contract",
    "part", "time", "full", "permanent", "how", "what", "when", "where",
    "why", "who", "can", "does", "the", "this", "that", "please", "many",
    "much", "days", "day", "paid", "unpaid", "have", "has", "had", "did",
    "about", "from", "with", "your", "their", "them", "they", "she", "her",
    "his", "him", "our", "you", "and", "for", "not", "are", "was", "were",
    "will", "would", "could", "should", "hr", "peoplehub", "friday",
    "saturday", "january", "march", "december", "xyz", "during", "after",
    "before", "under", "into", "per", "year", "years", "month", "months",
    "week", "weeks", "child", "children", "spouse", "parent", "parents",
    "mother", "father", "brother", "sister", "uncle", "aunt", "cousin",
    "nephew", "niece", "family", "medical", "certificate", "balance",
    "notice", "period", "probation", "confirmed", "confirmation", "holiday",
    "holidays", "public", "weekly", "working", "calendar", "basic", "salary",
    "without", "pay", "another", "other", "someone", "anyone", "everyone",
    "somebody", "my", "me", "mine", "line", "authorised", "authorized",
    "staff", "record", "records", "information", "reason", "reasons",
    "show", "tell", "give", "share", "each", "once", "only", "all", "any",
    "may", "must", "get", "take", "need", "needs", "human", "resources",
    "managing", "director", "yes", "off", "comp", "lwp", "immediate",
    "extended", "registered", "practitioner",
}
_NAME_PATTERNS = (
    re.compile(r"\b([a-z][a-z'-]{2,})'s\b", re.I),
    re.compile(r"\b(?:has|have|had|did|does|is|was|were|are)\s+([a-z][a-z'-]{2,})\b", re.I),
    re.compile(r"\bwhy\s+(?:is|was|are|were|did|does|has|have)\s+([a-z][a-z'-]{2,})\b", re.I),
)
# words that follow those verbs often and are never somebody's name
_NOT_A_NAME = {
    "there", "then", "this", "that", "these", "those", "today", "tomorrow",
    "yesterday", "last", "next", "still", "also", "already", "anyone",
    "everyone", "someone", "somebody", "anybody", "nobody", "something",
    "anything", "nothing", "such", "some", "one", "two", "three", "four",
    "five", "half", "more", "less", "most", "least", "unused", "exhausted",
    "enough", "possible", "true", "false", "correct", "right", "wrong",
    "allowed", "required", "entitled", "eligible", "covered", "available",
    "approved", "rejected", "treated", "counted", "credited", "deducted",
    "carried", "paid", "unpaid", "subject", "based", "same", "different",
}
_ABSENT_PHRASES = (
    "study leave",
    "half-day",
    "half day",
    "work from home",
    "working from home",
    "remote work",
    "sabbatical",
    "adoption leave",
    "adopt",
    "phone number",
    "mobile number",
)
_RELATIONS = {
    "spouse": ("spouse", "wife", "husband"),
    "child": ("child", "son", "daughter"),
    "parent": ("parent", "mother", "father", "mum", "dad"),
    "sibling": ("sibling", "brother", "sister"),
    "grandparent": ("grandparent", "grandmother", "grandfather", "grandma", "grandpa"),
    "parent-in-law": ("parent-in-law", "mother-in-law", "father-in-law"),
    "aunt": ("aunt",),
    "uncle": ("uncle",),
    "cousin": ("cousin",),
    "nephew": ("nephew",),
    "niece": ("niece",),
    "friend": ("friend",),
    "fiance": ("fiance", "fiancée", "fiancee", "fiancé"),
    "partner": ("partner",),
}
_SELF_RECORD = re.compile(
    r"\b("
    r"have i (already )?(taken|used)|"
    r"did i (already )?(take|use)|"
    r"i've (already )?(taken|used)|"
    r"i have (already )?(taken|used)|"
    r"my (current |remaining |unused )?leave balance|"
    r"days left|do i have left|how much leave do i have left|"
    r"how many days do i have left|"
    r"what is my salary|how much do i earn"
    r")\b",
    re.I,
)
_BLOCKERS = re.compile(
    r"\b(probation|notice period|during notice|notice|combin\w*|carry|carried|encash\w*|"
    r"certificate|in advance|consecutive|intern|consultant|part-time|part time|"
    r"contract employee|confirmed|confirmation|lapse|lapses|"
    r"father|mother|parent|spouse|child|sibling|uncle|aunt|grandparent|cousin|"
    r"wife|husband|son|daughter|brother|sister)\b",
    re.I,
)


def asks_for_other_personal_data(question: str) -> bool:
    text = _normalize(question)
    if _RULE_QUESTION.search(text):
        return False
    if not _PERSONAL_FACT.search(text):
        return False
    if _OTHER_PERSON.search(text) or _OTHER_POSSESSIVE.search(text):
        return True
    if re.search(r"\b(his|her)\b", text) and not re.search(r"\b(an employee|employees|a manager)\b", text):
        return True
    return bool(_names(text)) or bool(_capitalised_names(question))


def _capitalised_names(question: str) -> list[str]:
    """A capitalised word that is not policy wording and not sentence-initial."""
    found = []
    # "Mr. Hasan" must not read as the end of one sentence and the start of another
    plain = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr)\.", r"\1", str(question or "").strip())
    for sentence in re.split(r"(?<=[.!?])\s+", plain):
        words = re.findall(r"[A-Za-z][A-Za-z'\-]*", sentence)
        for index, word in enumerate(words):
            if index == 0 or len(word) < 3 or not word[0].isupper():
                continue
            if word.lower() in _STOP_NAMES or word.lower() in _NOT_A_NAME:
                continue
            found.append(word)
    return found


def is_hard_unknown(question: str, policy: PolicyDocument) -> bool:
    text = _normalize(question)
    policy_text = policy.text_lower
    if _SELF_RECORD.search(text):
        return True
    for phrase in _ABSENT_PHRASES:
        if phrase in text and phrase not in policy_text:
            return True
    if _unknown_bereavement_relation(text, policy):
        return True
    if _combination_unknown(text, policy):
        return True
    if _notice_gap_unknown(text, policy):
        return True
    if _public_holiday_count_unknown(text):
        return True
    return False


def privacy_message(policy: PolicyDocument) -> str:
    section = _confidentiality_section(policy)
    base = "I can't share another employee's personal information. Please contact HR."
    if section is None:
        return base
    return (
        f"{base} Leave records are confidential under "
        f"Section {section.id} ({section.heading})."
    )


def reconcile_answer(question: str, answer: str, citations: list[str], policy: PolicyDocument) -> tuple[str, list[str]] | None:
    """Replace a model answer when it contradicts the uploaded policy.

    Returns None when the model answer should be kept.
    """
    exclusion = _exclusion_fix(question, answer, policy)
    if exclusion is not None:
        return exclusion
    combination = _combination_fix(question, answer, policy)
    if combination is not None:
        return combination
    carried = _keyword_fix(question, answer, policy, topic="carry")
    if carried is not None:
        return carried
    encash = _keyword_fix(question, answer, policy, topic="encash")
    if encash is not None:
        return encash
    entitlement = _entitlement_fix(question, answer, policy)
    if entitlement is not None:
        return entitlement
    return None


def numbers_are_grounded(answer: str, policy: PolicyDocument) -> bool:
    corpus = policy.prompt_text()
    for token in re.findall(r"\d{1,2}:\d{2}|\d+\.\d+|\d+", answer):
        if token not in corpus:
            return False
    return True


def valid_citations(citations: list[str], policy: PolicyDocument) -> list[str]:
    seen: list[str] = []
    for citation in citations:
        section_id = str(citation).strip()
        if policy.section(section_id) and section_id not in seen:
            seen.append(section_id)
    return seen


def source_line(policy: PolicyDocument, citations: list[str]) -> str:
    labels = []
    for section_id in citations:
        section = policy.section(section_id)
        if section is not None:
            labels.append(f"Section {section.id} ({section.heading})")
    return "Source: " + "; ".join(labels) + "."


def _exclusion_fix(question: str, answer: str, policy: PolicyDocument) -> tuple[str, list[str]] | None:
    text = _normalize(question)
    groups = ("intern", "part-time", "part time", "contract employee", "consultant")
    if not any(group in text for group in groups):
        return None
    if not re.search(r"\b(cover\w*|entitl\w*|leaves?|apply|applies|eligible|how many|how much)\b", text):
        return None
    match = _exclusion_sentences(policy)
    if match is None:
        return None
    sentences, section = match
    quoted = " ".join(sentences)
    if _squash(quoted) in _squash(answer):
        return None
    if re.search(r"\bnot covered\b", answer, re.I):
        return None
    return quoted, [section.id]


def _combination_fix(question: str, answer: str, policy: PolicyDocument) -> tuple[str, list[str]] | None:
    text = _normalize(question)
    if not re.search(r"\bcombin", text):
        return None
    found = _combination_sentence(text, policy)
    if found is None:
        return None
    sentence, section = found
    denies = "not be combined" in sentence.lower() or "cannot be combined" in sentence.lower()
    missing = not answer.strip() or bool(re.search(r"\bi don't know\b", answer, re.I))
    if missing or (denies and _says_allowed(answer, "combined")):
        return sentence, [section.id]
    return None


def _keyword_fix(
    question: str, answer: str, policy: PolicyDocument, topic: str
) -> tuple[str, list[str]] | None:
    text = _normalize(question)
    if topic == "carry" and not re.search(r"\b(carry|carried)\b", text):
        return None
    if topic == "encash" and "encash" not in text:
        return None
    types = _mentioned_leave_types(text, policy)
    if len(types) != 1:
        return None
    section = _section_for_leave_type(types[0], policy)
    if section is None:
        return None
    verb = "carried" if topic == "carry" else "encashed"
    chosen = _sentences_for_topic(section, topic)
    if not chosen:
        return None
    quoted = " ".join(chosen)
    source_denies = _says_denied(quoted, verb)
    source_allows = _says_allowed(quoted, verb)
    missing = not answer.strip() or bool(re.search(r"\bi don't know\b", answer, re.I))
    contradicts = (source_denies and _says_allowed(answer, verb)) or (
        source_allows and _says_denied(answer, verb)
    )
    if contradicts or missing:
        return quoted, [section.id]
    return None


def _sentences_for_topic(section: Section, topic: str) -> list[str]:
    sentences = section.sentences()
    chosen: list[str] = []
    for index, sentence in enumerate(sentences):
        lowered = sentence.lower()
        matches = topic in lowered or (topic == "carry" and "carried" in lowered)
        if not matches:
            continue
        chosen.append(sentence)
        if index + 1 < len(sentences):
            nxt = sentences[index + 1]
            if nxt not in chosen and re.search(r"separation|lapse", nxt, re.I):
                chosen.append(nxt)
    return chosen


def _says_allowed(text: str, verb: str) -> bool:
    if _says_denied(text, verb):
        return False
    return bool(re.search(rf"\b(can|may)\s+be\s+{verb}\b", text, re.I))


def _says_denied(text: str, verb: str) -> bool:
    return bool(
        re.search(rf"\b(cannot|can't|may not|must not|not)\s+be\s+{verb}\b", text, re.I)
        or re.search(rf"\bnot\s+{verb}\b", text, re.I)
    )


def _entitlement_fix(question: str, answer: str, policy: PolicyDocument) -> tuple[str, list[str]] | None:
    text = _normalize(question)
    if _BLOCKERS.search(text):
        return None
    if any(group in text for group in ("intern", "consultant", "part-time", "part time", "contract")):
        return None
    types = _mentioned_leave_types(text, policy)
    if len(types) != 1:
        return None
    row = next(item for item in policy.entitlements if item.leave_type == types[0])
    asks_count = bool(re.search(r"\b(how many|how much|how long|entitl\w*|per year|per child)\b", text))
    asks_paid = bool(re.search(r"\b(is|are)\b.{0,40}\bpaid\b|\bpaid or unpaid\b|\bdo i get paid\b", text))
    if not asks_count and not asks_paid:
        return None
    citations = []
    for section in policy.sections:
        blob = section.text.lower()
        if row.leave_type.lower() in blob and row.entitlement.lower() in blob:
            citations.append(section.id)
            break
    if not citations and policy.section("4.0"):
        citations.append("4.0")
    if row.section and policy.section(row.section) and row.section not in citations:
        citations.append(row.section)
    if asks_paid and not asks_count:
        paid = row.paid.strip().lower()
        if not answer.strip() or (paid == "yes" and re.search(r"\bnot paid\b|\bunpaid\b", answer, re.I)):
            if paid == "yes":
                return f"{row.leave_type} is paid. The entitlement is {row.entitlement}.", citations
        if paid == "no" and (not answer.strip() or (re.search(r"\bis paid\b", answer, re.I) and "not" not in answer.lower())):
            return f"{row.leave_type} is not paid. The entitlement is {row.entitlement}.", citations
        return None
    numbers = re.findall(r"\d+\.\d+|\d+", row.entitlement)
    if numbers and numbers[0] in answer:
        return None
    paid_sentence = ""
    if row.paid.strip().lower() == "yes":
        paid_sentence = " It is paid."
    elif row.paid.strip().lower() == "no":
        paid_sentence = " It is not paid."
    return f"{row.leave_type}: {row.entitlement}.{paid_sentence}", citations


def _combination_unknown(text: str, policy: PolicyDocument) -> bool:
    if not re.search(r"\bcombin", text):
        return False
    types = _mentioned_leave_types(text, policy)
    if len(types) < 2:
        return False
    return _combination_sentence(text, policy) is None


def _combination_sentence(text: str, policy: PolicyDocument) -> tuple[str, Section] | None:
    types = _mentioned_leave_types(text, policy)
    if len(types) < 2:
        return None
    for section in policy.sections:
        for sentence in section.sentences():
            lowered = sentence.lower()
            if "combin" in lowered and all(leave_type.lower() in lowered for leave_type in types):
                return sentence, section
    return None


def _notice_gap_unknown(text: str, policy: PolicyDocument) -> bool:
    if not re.search(r"notice period|serving notice|during (my |the )?notice\b", text):
        return False
    types = _mentioned_leave_types(text, policy)
    if not types and re.search(
        r"how long|how many (working |calendar )?(days|weeks|months)|length|duration|"
        r"what is (the )?notice period|notice period (for|when|on)",
        text,
    ):
        return "notice period is" not in policy.text_lower and "notice period of" not in policy.text_lower
    if not types:
        return False
    notice_text = " ".join(
        section.text
        for section in policy.sections
        if "notice period" in section.text.lower() or "notice period" in section.heading.lower()
    ).lower()
    for leave_type in types:
        short = leave_type.lower().removesuffix(" leave")
        if leave_type.lower() not in notice_text and short not in notice_text:
            return True
    return False


def _public_holiday_count_unknown(text: str) -> bool:
    return bool(
        re.search(
            r"how many public holidays|number of public holidays|list (all )?public holidays|"
            r"what are the public holidays|which public holidays",
            text,
        )
    )


def _unknown_bereavement_relation(text: str, policy: PolicyDocument) -> bool:
    if not re.search(r"bereavement|passed away|pass away|died|death|funeral", text):
        return False
    bereavement = _bereavement_text(policy)
    mentioned = False
    unknown = False
    for canonical, words in _RELATIONS.items():
        if not any(re.search(rf"\b{re.escape(word)}\b", text) for word in words):
            continue
        mentioned = True
        known = any(re.search(rf"\b{re.escape(word)}\b", bereavement) for word in words)
        known = known or re.search(rf"\b{re.escape(canonical)}\b", bereavement) is not None
        if not known:
            unknown = True
    return mentioned and unknown


def _bereavement_text(policy: PolicyDocument) -> str:
    chunks = [
        section.text
        for section in policy.sections
        if "bereavement" in section.heading.lower() or "bereavement" in section.text.lower()
    ]
    return " ".join(chunks).lower()


def _exclusion_sentences(policy: PolicyDocument) -> tuple[list[str], Section] | None:
    for section in policy.sections:
        sentences = section.sentences()
        for index, sentence in enumerate(sentences):
            if "not covered" in sentence.lower():
                chosen = [sentence]
                if index + 1 < len(sentences) and "contract" in sentences[index + 1].lower():
                    chosen.append(sentences[index + 1])
                return chosen, section
    return None


def _mentioned_leave_types(text: str, policy: PolicyDocument) -> list[str]:
    found: list[str] = []
    for row in policy.entitlements:
        if any(re.search(rf"\b{re.escape(alias)}\b", text) for alias in _aliases(row.leave_type)):
            found.append(row.leave_type)
    return found


def _aliases(leave_type: str) -> list[str]:
    base = leave_type.lower()
    names = [base]
    if base.endswith(" leave"):
        short = base[: -len(" leave")]
        names.extend([f"{short} leave", f"{short} days", f"{short} day"])
    if "compensatory" in base:
        names.extend(["compensatory off", "comp off", "compensatory", "time off in lieu", "toil"])
    return names


def _section_for_leave_type(leave_type: str, policy: PolicyDocument) -> Section | None:
    row = next(item for item in policy.entitlements if item.leave_type == leave_type)
    if row.section and policy.section(row.section):
        return policy.section(row.section)
    for section in policy.sections:
        if leave_type.lower() in section.heading.lower():
            return section
    return None


def _confidentiality_section(policy: PolicyDocument) -> Section | None:
    for section in policy.sections:
        if "confidential" in section.heading.lower():
            return section
    for section in policy.sections:
        if "confidential" in section.text.lower():
            return section
    return None


def _names(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _NAME_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1).lower()
            if name in _STOP_NAMES or name in _NOT_A_NAME or name in found:
                continue
            found.append(name)
    return found


def _normalize(text: str) -> str:
    return text.replace("’", "'").replace("“", '"').replace("”", '"').lower()


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()
