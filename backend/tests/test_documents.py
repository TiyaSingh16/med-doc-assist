import uuid

from app.models.document import Document
from app.routers import documents as documents_router
from app.services.pdf_service import ExtractionError
from tests.conftest import make_pdf, register_and_login

TEXT = "Hemoglobin 13.5 g/dL. Fasting glucose 92 mg/dL. " * 5


def upload(client, headers, data=None, name="report.pdf"):
    data = data if data is not None else make_pdf([TEXT])
    return client.post("/documents/upload", headers=headers, files={"file": (name, data, "application/pdf")})


def test_upload_non_pdf_rejected(client, auth_headers):
    response = client.post(
        "/documents/upload", headers=auth_headers, files={"file": ("test.txt", b"hello world", "text/plain")}
    )
    assert response.status_code == 400


def test_upload_without_auth_rejected(client):
    response = client.post("/documents/upload", files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")})
    assert response.status_code == 401


def test_get_documents_requires_auth(client):
    assert client.get("/documents/").status_code == 401


def test_renamed_non_pdf_is_rejected_by_content(client, auth_headers, fake_storage):
    response = upload(client, auth_headers, data=b"MZ\x90\x00 an .exe renamed to .pdf")
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]
    assert fake_storage == []  # nothing stored


def test_oversized_upload_is_rejected_with_413(client, auth_headers, fake_storage, monkeypatch):
    monkeypatch.setattr(documents_router.settings, "max_upload_bytes", 1000)
    response = upload(client, auth_headers, data=b"%PDF-" + b"0" * 2000)
    assert response.status_code == 413
    assert fake_storage == []


def test_upload_processes_document_and_never_exposes_storage_location(
    client, auth_headers, fake_storage, fake_embeddings
):
    response = upload(client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert "file_path" not in body
    assert fake_storage[0]["type"] == "private"

    # TestClient runs background tasks before returning, so processing is done.
    doc = client.get(f"/documents/{body['id']}", headers=auth_headers).json()
    assert doc["processing_status"] == "completed"
    assert doc["processing_error"] is None


def test_unreadable_document_fails_with_a_user_facing_reason(client, auth_headers, fake_storage, monkeypatch):
    def no_text(path):
        raise ExtractionError("No readable text was found in this document.")

    monkeypatch.setattr(documents_router, "smart_extract", no_text)
    doc_id = upload(client, auth_headers).json()["id"]
    doc = client.get(f"/documents/{doc_id}", headers=auth_headers).json()
    assert doc["processing_status"] == "failed"
    assert doc["processing_error"] == "No readable text was found in this document."


def test_unexpected_processing_error_is_logged_but_shown_generically(client, auth_headers, fake_storage, monkeypatch):
    def boom(text, doc_id):
        raise RuntimeError("chromadb internal: sqlite3.OperationalError at /app/chroma_db")

    monkeypatch.setattr(documents_router, "embed_document", boom)
    doc_id = upload(client, auth_headers).json()["id"]
    doc = client.get(f"/documents/{doc_id}", headers=auth_headers).json()
    assert doc["processing_status"] == "failed"
    assert "chromadb" not in doc["processing_error"]


def test_users_cannot_see_each_others_documents(client, fake_storage, fake_embeddings):
    alice = register_and_login(client)
    bob = register_and_login(client)
    doc_id = upload(client, alice).json()["id"]

    assert client.get(f"/documents/{doc_id}", headers=bob).status_code == 404
    assert client.get("/documents/", headers=bob).json()["total"] == 0
    assert client.get(f"/chat/{doc_id}/history", headers=bob).status_code == 404
    assert client.post(f"/documents/{doc_id}/extract", headers=bob).status_code == 404


def test_malformed_document_id_is_a_client_error_not_a_500(client, auth_headers):
    assert client.get("/documents/not-a-uuid", headers=auth_headers).status_code == 422
    assert client.get(f"/documents/{uuid.uuid4()}", headers=auth_headers).status_code == 404


def test_background_task_uses_its_own_session(fake_storage, monkeypatch, tmp_path):
    """process_document must not depend on the request's (closed) session."""
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    user = User(email="bg@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    doc = Document(user_id=user.id, filename="a.pdf", file_path="k", processing_status="processing")
    db.add(doc)
    db.commit()
    doc_id = str(doc.id)
    db.close()  # like the request finishing

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(make_pdf([TEXT]))
    monkeypatch.setattr(documents_router, "embed_document", lambda text, d: 3)
    documents_router.process_document(doc_id, str(pdf))

    db = SessionLocal()
    assert db.get(Document, uuid.UUID(doc_id)).processing_status == "completed"
    db.close()
    assert not pdf.exists()  # temp file cleaned up
