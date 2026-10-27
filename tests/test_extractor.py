from pathlib import Path

from app.services.extractor import extract_policy

SAMPLE = Path(__file__).resolve().parents[1] / "XYZ Company Leave Policy (Sample).pdf"


def test_sample_policy_sections_and_table():
    policy = extract_policy(SAMPLE.read_bytes(), SAMPLE.name)

    assert policy.page_count == 6
    assert policy.metadata["Policy number"] == "HR-POL-004"
    assert policy.metadata["Version"] == "2.0"
    assert policy.metadata["Applies to"] == "All permanent full-time employees"

    by_type = {row.leave_type: row for row in policy.entitlements}
    assert by_type["Casual Leave"].entitlement == "8 working days per year"
    assert by_type["Sick Leave"].entitlement == "12 working days per year"
    assert by_type["Annual Leave"].entitlement == "20 working days per year"
    assert by_type["Paternity Leave"].entitlement == "7 calendar days per child"

    casual = policy.section("4.2")
    sick = policy.section("4.3")
    scope = policy.section("2.3")
    notice = policy.section("7")
    contact = policy.section("11.2")
    holidays = policy.section("5.1")
    confidential = policy.section("9")

    assert casual is not None and "may not be combined" in casual.text
    assert sick is not None and "10:00 AM" in sick.text
    assert scope is not None and "not covered" in scope.text
    assert notice is not None and "notice period" in notice.text.lower()
    assert contact is not None and "hr@xyz-company.example" in contact.text
    assert holidays is not None and "Friday and Saturday" in holidays.text
    assert confidential is not None and "Confidential" in confidential.heading

    prompt = policy.prompt_text()
    assert "8 working days per year" in prompt
    assert "12 working days per year" in prompt
    assert "1.67 working days" in prompt
