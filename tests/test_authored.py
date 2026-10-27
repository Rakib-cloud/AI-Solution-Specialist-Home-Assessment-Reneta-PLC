from app.services.assistant import answer_question
from app.services.authored import _numbered, new_policy, sanitize, to_policy_document
from app.services.extractor import extract_policy
from app.services.pdf_export import render_policy_pdf


def _filled():
    draft = new_policy("blank")
    draft["title"] = "Test Company Leave Policy"
    draft["disclaimer"] = "This policy explains leave for permanent employees."
    draft["metadata"]["Policy number"] = "HR-POL-100"
    draft["metadata"]["Version"] = "1.0"
    draft["sections"] = [
        {
            "heading": "Purpose",
            "body": "This policy explains how permanent employees request leave.",
            "subsections": [],
        },
        {
            "heading": "Types of Leave",
            "body": "",
            "subsections": [
                {
                    "heading": "Summary of Entitlements",
                    "kind": "entitlements",
                    "body": "",
                    "clauses": [],
                    "rows": [
                        {
                            "leave_type": "Casual Leave",
                            "entitlement": "8 working days per year",
                            "paid": "Yes",
                            "section": "2.1",
                        }
                    ],
                },
                {
                    "heading": "Casual Leave",
                    "kind": "text",
                    "body": "",
                    "clauses": ["Unused Casual Leave cannot be carried forward."],
                    "rows": [],
                },
            ],
        },
    ]
    return sanitize(draft)


def test_authored_policy_answers_without_a_model():
    document = to_policy_document(_filled(), page_count=1)
    result = answer_question("How many casual leave days do I get?", document)
    assert result.kind == "answer"
    assert "8 working days" in result.text
    assert "Section 2.0" in result.text


def test_downloaded_pdf_uses_the_sample_numbering():
    draft = _filled()
    draft["status"] = "published"
    pdf_bytes = render_policy_pdf(draft)
    assert pdf_bytes.startswith(b"%PDF")
    extracted = extract_policy(pdf_bytes, "Test Company Leave Policy.pdf")
    headings = {section.id: section.heading for section in extracted.sections}
    assert headings["1"] == "Purpose"
    assert headings["2"] == "Types of Leave"
    assert "2.0" in headings
    assert "cannot be carried forward" in extracted.section("2.1").text
    assert "8 working days per year" in extracted.prompt_text()


def test_sample_policy_copies_the_pdf_structure():
    draft = new_policy("sample")
    numbers = []
    for number, _section, children in _numbered(draft):
        numbers.append(number)
        numbers.extend(child_id for child_id, _child in children)
    assert numbers[:8] == ["1", "2", "2.1", "2.2", "2.3", "3", "4", "4.0"]
    assert "4.2" in numbers
    assert "9" in numbers
    assert "11.2" in numbers
    document = to_policy_document(draft, page_count=6)
    assert document.metadata["Policy number"] == "HR-POL-004"
    assert any(row.leave_type == "Casual Leave" and "8 working" in row.entitlement for row in document.entitlements)
    assert any(row.leave_type == "Sick Leave" and "12 working" in row.entitlement for row in document.entitlements)
    casual = answer_question("How many casual leave days do I get in a year?", document)
    assert "8 working days" in casual.text
    assert "Section 4.0" in casual.text
    assert document.section("10") is not None
    assert "PeopleHub" in document.section("10").text
    assert document.section("10.1") is None


def test_seeded_sample_can_be_selected(client):
    listed = client.get("/api/authored")
    sample = next(item for item in listed.get_json()["policies"] if item["policy_number"] == "HR-POL-004")
    assert sample["status"] == "published"
    selected = client.post(f"/api/authored/{sample['id']}/select")
    assert selected.status_code == 200
    casual = client.post("/api/ask", json={"question": "How many casual leave days do I get in a year?"})
    assert "8 working days" in casual.get_json()["text"]
    unknown = client.post("/api/ask", json={"question": "Can I take study leave?"})
    assert unknown.get_json()["text"] == "I don't know, please contact HR."
    private = client.post("/api/ask", json={"question": "How many leave days has Rahim taken?"})
    assert private.get_json()["text"].startswith("I can't share another employee's personal information.")


def test_upload_on_the_policy_page_adds_a_selectable_policy(client):
    from pathlib import Path

    sample = Path(__file__).resolve().parents[1] / "XYZ Company Leave Policy (Sample).pdf"
    uploaded = client.post(
        "/api/authored/upload",
        data={"file": (sample.open("rb"), sample.name)},
        content_type="multipart/form-data",
    )
    body = uploaded.get_json()
    assert uploaded.status_code == 201
    assert body["metadata"]["Policy number"] == "HR-POL-004"
    listed = client.get("/api/authored").get_json()["policies"]
    assert any(item["id"] == body["id"] and item["status"] == "published" for item in listed)


def test_view_opens_the_policy_as_a_pdf(client):
    listed = client.get("/api/authored")
    sample = next(item for item in listed.get_json()["policies"] if item["policy_number"] == "HR-POL-004")
    page = client.get(f"/policies/{sample['id']}/view")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "viewer-frame" in html
    assert sample["title"] in html
    preview = client.get(f"/api/authored/{sample['id']}/preview")
    assert preview.status_code == 200
    assert preview.data.startswith(b"%PDF")
    assert preview.mimetype == "application/pdf"
    assert "inline" in preview.headers["Content-Disposition"]
    missing = client.get("/policies/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/view")
    assert missing.status_code == 404


def test_publish_and_select_roundtrip(client):
    created = client.post("/api/authored", json={"kind": "blank"})
    draft = created.get_json()
    draft["title"] = "Desk Leave Policy"
    draft["sections"][0]["body"] = "Employees must request leave through the portal."
    saved = client.put(f"/api/authored/{draft['id']}", json=draft)
    assert saved.status_code == 200

    blocked = client.post(f"/api/authored/{draft['id']}/select")
    assert blocked.status_code == 400

    published = client.post(f"/api/authored/{draft['id']}/publish")
    body = published.get_json()
    assert published.status_code == 200
    assert body["title"] == "Desk Leave Policy"
    assert body["chat_enabled"] is True

    answer = client.post("/api/ask", json={"question": "How do employees request leave?"})
    assert answer.get_json()["kind"] == "answer"
    assert "portal" in answer.get_json()["text"].lower()

    download = client.get(f"/api/authored/{draft['id']}/pdf")
    assert download.status_code == 200
    assert download.data.startswith(b"%PDF")

    page = client.get("/policies")
    text = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Create policy" in text
    assert "Create manually" in text
    assert "Sample policy" in text
    assert 'type="file"' in text
    assert 'id="nav-toggle"' in text
    assert 'id="sidebar"' in text
    assert 'class="data"' in text
    assert "Policies" in text
    assert "Assistant" in text
    assert "No API key is used" not in text
