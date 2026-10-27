from io import BytesIO
from pathlib import Path

from app import create_app
from app.config import Settings
from app.services.grounded import UNKNOWN_MESSAGE

SAMPLE = Path(__file__).resolve().parents[1] / "XYZ Company Leave Policy (Sample).pdf"


def _upload(client):
    return client.post(
        "/api/policy",
        data={"file": (SAMPLE.open("rb"), SAMPLE.name)},
        content_type="multipart/form-data",
    )


def test_homepage_has_the_three_demo_questions(client):
    response = client.get("/")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Leave Policy Assistant" in page
    assert "How many casual leave days do I get in a year?" in page
    assert "Can I take study leave?" in page
    assert "How many leave days has Rahim taken?" in page


def test_upload_analyses_the_sample_policy(client):
    response = _upload(client)
    data = response.get_json()
    assert response.status_code == 200
    assert data["ready"] is True
    assert data["chat_enabled"] is True
    assert data["metadata"]["Policy number"] == "HR-POL-004"
    assert any(row["leave_type"] == "Casual Leave" and "8 working" in row["entitlement"] for row in data["entitlements"])
    assert any("permanent full-time" in item["quote"] for item in data["quotes"])

    again = client.get("/api/policy")
    assert again.status_code == 200
    assert again.get_json()["policy_id"] == data["policy_id"]


def test_three_required_behaviours(client, fake_llm):
    assert _upload(client).status_code == 200

    covered = client.post("/api/ask", json={"question": "How many casual leave days do I get in a year?"})
    covered_body = covered.get_json()
    assert covered_body["kind"] == "answer"
    assert "8 working days" in covered_body["text"]
    assert "15" not in covered_body["text"]
    assert "Section 4.0" in covered_body["text"]

    missing = client.post("/api/ask", json={"question": "Can I take study leave?"})
    assert missing.get_json()["kind"] == "unknown"
    assert missing.get_json()["text"] == UNKNOWN_MESSAGE
    assert missing.get_json()["citations"] == []
    assert fake_llm.calls == 0

    private = client.post("/api/ask", json={"question": "How many leave days has Rahim taken?"})
    private_body = private.get_json()
    assert private_body["kind"] == "privacy"
    assert private_body["text"].startswith("I can't share another employee's personal information.")
    assert "Please contact HR." in private_body["text"]
    assert "Section 9" in private_body["text"]
    assert fake_llm.calls == 0


def test_model_cannot_invent_an_intern_entitlement_or_skip_a_stated_rule(client):
    assert _upload(client).status_code == 200

    interns = client.post("/api/ask", json={"question": "How many annual leave days do interns get?"})
    assert "not covered" in interns.get_json()["text"].lower()
    assert "Section 2.3" in interns.get_json()["text"]

    sick = client.post("/api/ask", json={"question": "Can I carry forward unused sick leave?"})
    assert "cannot be carried" in sick.get_json()["text"].lower()
    assert "Section 4.3" in sick.get_json()["text"]

    certificate = client.post("/api/ask", json={"question": "When do I need a medical certificate for sick leave?"})
    body = certificate.get_json()
    assert body["kind"] == "answer"
    assert "2 consecutive working days" in body["text"]
    assert "Section 4.3" in body["text"]


def test_checked_rules_answer_without_an_api_key(tmp_path):
    settings = Settings(
        secret_key="test-secret",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        openai_base_url="",
        storage_dir=tmp_path / "storage",
    )
    client = create_app(settings).test_client()
    uploaded = _upload(client).get_json()
    assert uploaded["model_enabled"] is False
    assert uploaded["chat_enabled"] is True

    covered = client.post("/api/ask", json={"question": "How many casual leave days do I get in a year?"})
    assert "8 working days" in covered.get_json()["text"]
    assert "Section 4.0" in covered.get_json()["text"]

    missing = client.post("/api/ask", json={"question": "Can I take study leave?"})
    assert missing.get_json()["text"] == UNKNOWN_MESSAGE

    private = client.post("/api/ask", json={"question": "How many leave days has Rahim taken?"})
    assert private.get_json()["kind"] == "privacy"
    assert "Section 9" in private.get_json()["text"]

    interns = client.post("/api/ask", json={"question": "Are interns covered by this policy?"})
    assert "not covered" in interns.get_json()["text"].lower()
    assert "Section 2.3" in interns.get_json()["text"]

    certificate = client.post("/api/ask", json={"question": "When do I need a medical certificate for sick leave?"})
    assert certificate.status_code == 200
    assert "2 consecutive working days" in certificate.get_json()["text"]


def test_rejected_upload(client):
    response = client.post(
        "/api/policy",
        data={"file": (BytesIO(b"not a pdf"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
