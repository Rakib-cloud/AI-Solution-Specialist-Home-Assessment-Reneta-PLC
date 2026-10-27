from __future__ import annotations

import re
from pathlib import Path

from io import BytesIO

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file, session

from app.config import Settings
from app.services.assistant import analyze_policy, answer_question
from app.services.authored import (
    DraftStore,
    new_policy,
    sanitize,
    template_defaults,
    to_policy_document,
    validate_for_publish,
)
from app.services.extractor import extract_policy
from app.services.importer import draft_from_pdf, ensure_sample_policy
from app.services.models import PolicyDocument
from app.services.pdf_export import render_policy_pdf
from app.services.store import PolicyStore

bp = Blueprint("main", __name__)


@bp.context_processor
def navigation():
    endpoint = request.endpoint or ""
    if endpoint in {"main.policies", "main.edit_policy", "main.view_policy"}:
        active = "policies"
    elif endpoint == "main.index":
        active = "assistant"
    else:
        active = ""
    return {"active": active}


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/policies")
def policies():
    return render_template("policies.html")


@bp.get("/policies/<policy_id>")
def edit_policy(policy_id):
    return render_template("editor.html", policy_id=policy_id)


@bp.get("/policies/<policy_id>/view")
def view_policy(policy_id):
    draft = _drafts().load(policy_id)
    if draft is None:
        abort(404)
    title = draft.get("title") or "Policy"
    return render_template("viewer.html", policy_id=policy_id, title=title)


@bp.get("/api/health")
def health():
    return jsonify(ok=True, chat_enabled=True, mode="local")


@bp.get("/api/policy")
def current_policy():
    policy = _current_policy()
    if policy is None:
        return jsonify(ready=False), 404
    analysis = _store().load_analysis(policy.id)
    return jsonify(_public_policy(policy, analysis["quotes"], analysis["warning"]))


@bp.post("/api/policy")
def upload_policy():
    filename, pdf_bytes, error = _uploaded_pdf()
    if error is not None:
        return error
    try:
        policy = extract_policy(pdf_bytes, filename)
    except Exception:
        return jsonify(error="The PDF could not be read. Upload a text-based policy PDF."), 400
    if len(policy.prompt_text()) < 200 or not policy.sections:
        return jsonify(error="This PDF has too little readable text. Upload a text-based policy."), 400

    quotes = analyze_policy(policy)
    store = _store()
    store.save(policy, pdf_bytes)
    store.save_analysis(policy.id, quotes, None)
    session["policy_id"] = policy.id
    session.permanent = True
    return jsonify(_public_policy(policy, quotes, None))


@bp.post("/api/ask")
def ask():
    policy = _current_policy()
    if policy is None:
        return jsonify(error="Upload a PDF or select a published policy first."), 400
    body = request.get_json(silent=True) or {}
    question = str(body.get("question") or "").strip()
    if not question:
        return jsonify(error="Type a question first."), 400
    if len(question) > 1000:
        return jsonify(error="Ask a shorter question (1,000 characters or fewer)."), 400
    result = answer_question(question, policy)
    return jsonify(kind=result.kind, text=result.text, citations=result.citations)


@bp.get("/api/authored")
def list_authored():
    ensure_sample_policy(_settings().storage_dir)
    return jsonify(policies=_drafts().list_all())


@bp.post("/api/authored/upload")
def upload_authored():
    filename, pdf_bytes, error = _uploaded_pdf()
    if error is not None:
        return error
    try:
        draft = draft_from_pdf(pdf_bytes, filename, status="published")
    except Exception:
        return jsonify(error="The PDF could not be read. Upload a text-based policy PDF."), 400
    document = to_policy_document(draft)
    if len(document.prompt_text()) < 200 or not document.sections:
        return jsonify(error="This PDF has too little readable text. Upload a text-based policy."), 400
    saved = _drafts().save(draft)
    public = _issue(saved, select=False)
    public["id"] = saved["id"]
    public["status"] = saved["status"]
    return jsonify(public), 201


@bp.post("/api/authored")
def create_authored():
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "blank")
    metadata = body.get("metadata")
    entitlements = body.get("entitlements")
    draft = _drafts().save(
        new_policy(
            "sample" if kind == "sample" else "blank",
            title=str(body.get("title") or "") or None,
            metadata=metadata if isinstance(metadata, dict) else None,
            entitlements=entitlements if isinstance(entitlements, list) else None,
        )
    )
    return jsonify(draft), 201


@bp.post("/api/authored/draft")
def build_authored():
    """Build a policy and hand it back unsaved, for the editor to store on save."""
    body = request.get_json(silent=True) or {}
    kind = str(body.get("kind") or "blank")
    metadata = body.get("metadata")
    entitlements = body.get("entitlements")
    return jsonify(
        new_policy(
            "sample" if kind == "sample" else "blank",
            title=str(body.get("title") or "") or None,
            metadata=metadata if isinstance(metadata, dict) else None,
            entitlements=entitlements if isinstance(entitlements, list) else None,
        )
    )


@bp.get("/api/authored/template")
def authored_template():
    return jsonify(template_defaults())


@bp.get("/api/authored/<policy_id>")
def read_authored(policy_id):
    draft = _drafts().load(policy_id)
    if draft is None:
        return jsonify(error="That policy was not found."), 404
    return jsonify(draft)


@bp.put("/api/authored/<policy_id>")
def update_authored(policy_id):
    """Save the policy at this id, creating it if the first save has not happened."""
    if not _valid_id(policy_id):
        return jsonify(error="That policy was not found."), 404
    current = _drafts().load(policy_id)
    incoming = request.get_json(silent=True) or {}
    incoming["id"] = policy_id
    incoming["status"] = current["status"] if current else "draft"
    draft = _drafts().save(sanitize(incoming))
    return jsonify(draft), 200 if current else 201


@bp.delete("/api/authored/<policy_id>")
def delete_authored(policy_id):
    if not _drafts().delete(policy_id):
        return jsonify(error="That policy was not found."), 404
    return jsonify(ok=True)


@bp.post("/api/authored/<policy_id>/publish")
def publish_authored(policy_id):
    draft = _drafts().load(policy_id)
    if draft is None:
        return jsonify(error="That policy was not found."), 404
    errors = validate_for_publish(draft)
    if errors:
        return jsonify(error=errors[0]), 400
    draft["status"] = "published"
    return jsonify(_issue(draft, select=True))


@bp.post("/api/authored/<policy_id>/unpublish")
def unpublish_authored(policy_id):
    draft = _drafts().load(policy_id)
    if draft is None:
        return jsonify(error="That policy was not found."), 404
    draft["status"] = "draft"
    return jsonify(_drafts().save(draft))


@bp.post("/api/authored/<policy_id>/select")
def select_authored(policy_id):
    draft = _drafts().load(policy_id)
    if draft is None:
        return jsonify(error="That policy was not found."), 404
    if draft.get("status") != "published":
        return jsonify(error="Publish the policy before using it in the assistant."), 400
    public = _issue(draft, select=True)
    return jsonify(public)


@bp.get("/api/authored/<policy_id>/pdf")
def download_authored(policy_id):
    return _pdf_response(policy_id, attachment=True)


@bp.get("/api/authored/<policy_id>/preview")
def preview_authored(policy_id):
    return _pdf_response(policy_id, attachment=False)


def _pdf_response(policy_id: str, attachment: bool):
    draft = _drafts().load(policy_id)
    if draft is None:
        return jsonify(error="That policy was not found."), 404
    pdf_bytes = render_policy_pdf(draft)
    name = to_policy_document(draft).filename
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=attachment,
        download_name=name,
    )


def _valid_id(policy_id: str) -> bool:
    return bool(re.fullmatch(r"[a-f0-9]{32}", policy_id or ""))


def _settings() -> Settings:
    return current_app.config["SETTINGS"]


def _store() -> PolicyStore:
    return PolicyStore(_settings().storage_dir)


def _drafts() -> DraftStore:
    return DraftStore(_settings().storage_dir)


def _issue(draft: dict, select: bool) -> dict:
    pdf_bytes = render_policy_pdf(draft)
    try:
        import pdfplumber

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
    except Exception:
        page_count = 1
    document = to_policy_document(draft, page_count)
    quotes = analyze_policy(document)
    store = _store()
    store.save(document, pdf_bytes)
    store.save_analysis(document.id, quotes, None)
    saved = _drafts().save(draft)
    if select:
        session["policy_id"] = document.id
        session.permanent = True
    public = _public_policy(document, quotes, None)
    public["status"] = saved["status"]
    return public


def _current_policy() -> PolicyDocument | None:
    policy_id = session.get("policy_id")
    if not policy_id:
        return None
    return _store().load(policy_id)


def _public_policy(policy: PolicyDocument, quotes: list[dict], warning: str | None) -> dict:
    return {
        "ready": True,
        "chat_enabled": True,
        "model_enabled": False,
        "warning": warning,
        "policy_id": policy.id,
        "filename": policy.filename,
        "title": policy.title,
        "page_count": policy.page_count,
        "metadata": policy.metadata,
        "entitlements": [row.to_dict() for row in policy.entitlements],
        "sections": [
            {"id": section.id, "heading": section.heading, "excerpt": section.excerpt()}
            for section in policy.sections
        ],
        "quotes": quotes,
    }


def _uploaded_pdf():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return "", b"", (jsonify(error="Choose a PDF to upload."), 400)
    filename = _clean_filename(upload.filename)
    if not filename.lower().endswith(".pdf"):
        return "", b"", (jsonify(error="Upload a PDF file."), 400)
    pdf_bytes = upload.read()
    if not pdf_bytes.startswith(b"%PDF"):
        return "", b"", (jsonify(error="That file is not a readable PDF."), 400)
    return filename, pdf_bytes, None


def _clean_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ()]", "", base).strip()
    return cleaned or "policy.pdf"
