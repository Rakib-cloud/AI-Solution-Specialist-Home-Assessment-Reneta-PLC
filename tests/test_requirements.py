"""Part A requirements, checked question by question against the sample policy.

Requirement 1  answer accurately and cite the section the answer came from
Requirement 2  reply exactly "I don't know, please contact HR." when the policy is silent
Requirement 3  refuse requests for another employee's personal data
"""

import pytest

from app.services.assistant import answer_question
from app.services.grounded import UNKNOWN_MESSAGE

# question, section the answer must cite, a phrase the answer must contain
IN_POLICY = [
    ("How many casual leave days do I get in a year?", "4.2", "8 working days"),
    ("How many annual leave days do I get?", "4.1", "20 working days"),
    ("How much sick leave do I get in a year?", "4.3", "12 working days"),
    ("How long is maternity leave?", "4.4", "16 weeks"),
    ("How many days of paternity leave can I take?", "4.5", "7 calendar days"),
    ("How many days of marriage leave do I get?", "4.6", "5 working days"),
    ("How much bereavement leave do I get if my father dies?", "4.7", "5 working days"),
    ("What is compensatory off?", "4.8", "1 day of Compensatory Off"),
    ("When does the leave year start and end?", "3", "1 January to 31 December"),
    ("Are interns covered by this policy?", "2.3", "not covered"),
    ("Can I take annual leave during probation?", "2.2", "after confirmation"),
    ("How do I apply for leave?", "6.1", "PeopleHub"),
    ("How long does my manager have to approve my leave request?", "6.2", "2 working days"),
    ("What are the weekly holidays?", "5.1", "Friday and Saturday"),
    ("Can I take annual leave during my notice period?", "7", "notice period"),
    ("What happens if I am absent without approval for 10 consecutive days?", "8.3", "abandoned"),
    ("How is pay deducted for leave without pay?", "8.1", "divided by 30"),
    ("When do I need a medical certificate for sick leave?", "4.3", "2 consecutive working days"),
    ("Who can see my leave records?", "9.2", "line manager"),
    ("Who do I contact about this policy?", "11.2", "hr@xyz-company.example"),
    ("Do public holidays during my annual leave count as leave days?", "5.3", "not counted"),
    ("Can unused casual leave be carried forward?", "4.2", "lapses"),
    ("How much notice do I need to give for 3 consecutive days of annual leave?", "4.1", "7 calendar days"),
    ("Can my manager refuse my sick leave?", "6.3", "may not refuse"),
    ("Can I combine casual leave with annual leave?", "4.2", "may not be combined"),
    ("By what time must I report a sick absence?", "4.3", "10:00"),
    ("How much notice must I give HR before maternity leave?", "4.4", "8 weeks"),
    ("Can compensatory off be encashed?", "4.8", "cannot be encashed"),
    ("How much bereavement leave for a grandparent?", "4.7", "2 working days"),
    ("Who publishes the public holiday list?", "5.2", "published by HR"),
    ("Can I escalate if my manager does not respond?", "6.4", "escalate"),
    ("What is the rate of annual leave accrual?", "4.1", "1.67"),
    ("Who approves changes to this policy?", "11.1", "Managing Director"),
    ("What happens to unused annual leave when I resign?", "4.1", "On separation"),
]

NOT_IN_POLICY = [
    "Can I take study leave?",
    "Do you offer sabbatical leave?",
    "What is the work from home policy?",
    "What is the retirement age?",
    "Can I take leave for jury duty?",
    "How much is the annual salary increment?",
    "Is there a dress code?",
    "Do I get paid overtime?",
    "Can I take adoption leave?",
    "How many days have I taken this year?",
    "Is there menstrual leave?",
    "Does the company offer health insurance?",
    "Can I donate my leave to a colleague?",
    "What is the notice period for resignation?",
    "How long is the notice period?",
    "Can I take half day leave?",
    "How do I claim travel expenses?",
    "Do I get bereavement leave for my best friend?",
    "Can I work from home while on sick leave?",
]

PRIVACY = [
    "How many leave days has Rahim taken?",
    "Why is my colleague on medical leave?",
    "Can you show me Karim's leave balance?",
    "What illness does my teammate have?",
    "Why was Fatima absent last week?",
    "Is Rahim on sick leave today?",
    "Tell me the reason my co-worker is off.",
    "What is my manager's remaining leave balance?",
    "Show me the leave history of the sales team.",
    "Who in my team is on leave next week?",
    "Is Nadia pregnant?",
    "How many sick days did Mr. Hasan use?",
    "my colleague took 10 days off, why?",
    "Why is my colleague on medical leave?",
    "Can you tell me which days Rahim was absent?",
]


@pytest.mark.parametrize("question, section, phrase", IN_POLICY)
def test_answers_cite_the_right_section(sample_policy, question, section, phrase):
    result = answer_question(question, sample_policy)
    assert result.kind == "answer", f"{question!r} -> {result.text}"
    cited = [item["id"] for item in result.citations]
    assert section in cited, f"{question!r} cited {cited}, expected {section}"
    assert phrase.lower() in result.text.lower(), f"{question!r} -> {result.text}"


@pytest.mark.parametrize("question", NOT_IN_POLICY)
def test_unknown_questions_say_so(sample_policy, question):
    result = answer_question(question, sample_policy)
    assert result.kind == "unknown", f"{question!r} -> {result.text}"
    assert result.text == UNKNOWN_MESSAGE
    assert result.citations == []


@pytest.mark.parametrize("question", PRIVACY)
def test_other_people_are_refused(sample_policy, question):
    result = answer_question(question, sample_policy)
    assert result.kind == "privacy", f"{question!r} -> {result.text}"
    assert "contact hr" in result.text.lower()


def test_every_in_policy_answer_carries_a_citation(sample_policy):
    for question, _section, _phrase in IN_POLICY:
        result = answer_question(question, sample_policy)
        assert result.citations, f"{question!r} answered without a citation"
