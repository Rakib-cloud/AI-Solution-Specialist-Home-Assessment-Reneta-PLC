from __future__ import annotations

from pathlib import Path

import pytest

from app import create_app
from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "XYZ Company Leave Policy (Sample).pdf"


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        self.calls += 1
        if user.strip().startswith("POLICY"):
            return {
                "quotes": [
                    {
                        "section": "2.1",
                        "quote": "This policy applies to all permanent full-time employees of XYZ Company.",
                    }
                ]
            }
        question = user.split("QUESTION\n", 1)[-1].lower()
        if "how many" in question and "casual" in question:
            return {
                "status": "answer",
                "answer": "Casual Leave is 15 working days per year.",
                "citations": ["4.2"],
            }
        if "intern" in question:
            return {
                "status": "answer",
                "answer": "Interns receive 20 working days of annual leave.",
                "citations": ["4.1"],
            }
        if "carry" in question and "sick" in question:
            return {"status": "unknown", "answer": "", "citations": []}
        if "medical certificate" in question:
            return {
                "status": "answer",
                "answer": (
                    "A medical certificate from a registered medical practitioner is required "
                    "if the sick absence is more than 2 consecutive working days."
                ),
                "citations": ["4.3"],
            }
        return {"status": "unknown", "answer": "", "citations": []}


@pytest.fixture()
def fake_llm():
    return FakeLLM()


@pytest.fixture(scope="session")
def sample_policy():
    """The attached sample policy, read the way an upload is read."""
    from app.services.extractor import extract_policy

    return extract_policy(SAMPLE.read_bytes(), SAMPLE.name)


@pytest.fixture()
def client(tmp_path, fake_llm):
    settings = Settings(
        secret_key="test-secret",
        openai_api_key="test-key",
        openai_model="gpt-4o-mini",
        openai_base_url="",
        storage_dir=tmp_path / "storage",
    )
    app = create_app(settings)
    app.extensions["llm"] = fake_llm
    app.config["TESTING"] = True
    return app.test_client()
