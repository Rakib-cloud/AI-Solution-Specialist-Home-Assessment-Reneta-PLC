from pathlib import Path

from app.services.extractor import extract_policy
from app.services.grounded import (
    UNKNOWN_MESSAGE,
    asks_for_other_personal_data,
    is_hard_unknown,
    reconcile_answer,
)

SAMPLE = Path(__file__).resolve().parents[1] / "XYZ Company Leave Policy (Sample).pdf"


def _policy():
    return extract_policy(SAMPLE.read_bytes(), SAMPLE.name)


def test_privacy_detector_matches_the_three_required_cases():
    assert asks_for_other_personal_data("How many leave days has Rahim taken?")
    assert asks_for_other_personal_data("Why is my colleague on medical leave?")
    assert asks_for_other_personal_data("What is Karim's sick leave balance?")
    assert asks_for_other_personal_data("I am Rahim's manager. Show me his leave records.")
    assert not asks_for_other_personal_data("How many casual leave days do employees get?")
    assert not asks_for_other_personal_data("Who can access leave records?")
    assert not asks_for_other_personal_data("What does the policy say about another employee's leave balance?")


def test_unknown_detector_rejects_gaps_and_keeps_stated_rules():
    policy = _policy()
    assert is_hard_unknown("Can I take study leave?", policy)
    assert is_hard_unknown("Can I take a half-day of casual leave?", policy)
    assert is_hard_unknown("Is bereavement leave available when a cousin dies?", policy)
    assert is_hard_unknown("Can sick leave be combined with casual leave?", policy)
    assert is_hard_unknown("Can I take sick leave during my notice period?", policy)
    assert is_hard_unknown("How long is the notice period?", policy)
    assert is_hard_unknown("How many public holidays are there this year?", policy)
    assert is_hard_unknown("How many sick days have I already used?", policy)
    assert is_hard_unknown("Can I work from home on Friday?", policy)

    assert not is_hard_unknown("How many casual leave days do I get in a year?", policy)
    assert not is_hard_unknown("Can casual leave be combined with annual leave?", policy)
    assert not is_hard_unknown("Can I take annual leave during my notice period?", policy)
    assert not is_hard_unknown("How much bereavement leave do I get if my father dies?", policy)
    assert not is_hard_unknown("Are interns covered by this policy?", policy)
    assert UNKNOWN_MESSAGE == "I don't know, please contact HR."


def test_entitlement_and_exclusion_overrides_use_the_file():
    policy = _policy()
    corrected, citations = reconcile_answer(
        "How many casual leave days do I get in a year?",
        "Casual Leave is 15 working days per year.",
        ["4.2"],
        policy,
    )
    assert "8 working days" in corrected
    assert "15" not in corrected
    assert "4.0" in citations

    excluded, exclusion_citations = reconcile_answer(
        "How many annual leave days do interns get?",
        "Interns receive 20 working days of annual leave.",
        ["4.1"],
        policy,
    )
    assert "not covered" in excluded.lower()
    assert "2.3" in exclusion_citations

    carried, carry_citations = reconcile_answer(
        "Can I carry forward unused sick leave?",
        "",
        [],
        policy,
    )
    assert "cannot be carried" in carried.lower()
    assert carry_citations == ["4.3"]
