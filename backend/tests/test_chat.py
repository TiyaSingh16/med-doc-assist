import json

from app.services.pdf_service import PAGE_SEPARATOR
from tests.conftest import make_pdf, register_and_login

PAGE_1 = "Patient: Jane Doe. Visit date 2026-03-01. Notes on general health. " * 4
PAGE_2 = "Hemoglobin 13.5 g/dL, reference 12.0-15.5. Platelets 250 x10^3/uL. " * 4


def ready_document(client, headers):
    response = client.post(
        "/documents/upload", headers=headers, files={"file": ("labs.pdf", make_pdf([PAGE_1, PAGE_2]), "application/pdf")}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_answer_includes_page_numbered_sources(client, auth_headers, fake_storage, fake_embeddings, fake_llm):
    doc_id = ready_document(client, auth_headers)
    response = client.post("/chat/query", headers=auth_headers, json={"document_id": doc_id, "question": "Hemoglobin?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("Your hemoglobin")
    assert body["chunks_used"] == len(body["sources"]) > 0
    assert {s["page"] for s in body["sources"]} <= {1, 2}
    assert all(s["excerpt"] for s in body["sources"])

    # The prompt fences the document off and labels each excerpt with its page.
    prompt = fake_llm["prompts"][0]
    assert "<document>" in prompt and "</document>" in prompt
    assert "| page 1]" in prompt or "| page 2]" in prompt


def test_history_returns_saved_sources(client, auth_headers, fake_storage, fake_embeddings, fake_llm):
    doc_id = ready_document(client, auth_headers)
    client.post("/chat/query", headers=auth_headers, json={"document_id": doc_id, "question": "Hemoglobin?"})
    history = client.get(f"/chat/{doc_id}/history", headers=auth_headers).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["sources"]


def test_streaming_answer_ends_with_sources_and_is_saved(client, auth_headers, fake_storage, fake_embeddings, fake_llm):
    doc_id = ready_document(client, auth_headers)
    with client.stream(
        "POST", "/chat/query/stream", headers=auth_headers, json={"document_id": doc_id, "question": "Hemoglobin?"}
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    done = [e for e in events if e["type"] == "done"]
    assert tokens == fake_llm["responses"][0]
    assert done and done[0]["sources"]
    history = client.get(f"/chat/{doc_id}/history", headers=auth_headers).json()
    assert history[-1]["content"] == tokens


def test_question_is_answered_after_vectors_were_lost(client, auth_headers, fake_storage, fake_embeddings, fake_llm):
    """A redeploy wiped Chroma; chat still works because the index is rebuilt."""
    from app.ai import embedder

    doc_id = ready_document(client, auth_headers)
    embedder.get_vectorstore(doc_id).reset_collection()
    response = client.post("/chat/query", headers=auth_headers, json={"document_id": doc_id, "question": "Platelets?"})
    assert response.status_code == 200
    assert response.json()["sources"]


def test_llm_failure_is_a_readable_502(client, auth_headers, fake_storage, fake_embeddings, monkeypatch):
    from app.ai import chains

    class Broken:
        def invoke(self, *a, **k):
            raise TimeoutError("deadline exceeded calling generativelanguage.googleapis.com")

    monkeypatch.setattr(chains, "get_llm", lambda **kw: Broken())
    doc_id = ready_document(client, auth_headers)
    response = client.post("/chat/query", headers=auth_headers, json={"document_id": doc_id, "question": "Hi?"})
    assert response.status_code == 502
    assert "googleapis" not in response.json()["detail"]


def test_llm_endpoints_are_rate_limited_per_user(client, fake_storage, fake_embeddings, fake_llm, monkeypatch):
    from app.utils.rate_limit import llm_limiter

    monkeypatch.setattr(llm_limiter, "limit", 2)
    alice = register_and_login(client)
    bob = register_and_login(client)
    doc_id = ready_document(client, alice)
    ask = {"document_id": doc_id, "question": "Hemoglobin?"}

    assert client.post("/chat/query", headers=alice, json=ask).status_code == 200
    assert client.post("/chat/query", headers=alice, json=ask).status_code == 200
    third = client.post("/chat/query", headers=alice, json=ask)
    assert third.status_code == 429
    assert int(third.headers["Retry-After"]) >= 1
    # Bob has his own budget (he gets 404 because it's not his document, not 429).
    assert client.post("/chat/query", headers=bob, json=ask).status_code == 404


def test_empty_question_is_rejected(client, auth_headers):
    response = client.post("/chat/query", headers=auth_headers, json={"document_id": "00000000-0000-0000-0000-000000000000", "question": ""})
    assert response.status_code == 422


def test_page_separator_never_leaks_into_sources(client, auth_headers, fake_storage, fake_embeddings, fake_llm):
    doc_id = ready_document(client, auth_headers)
    body = client.post("/chat/query", headers=auth_headers, json={"document_id": doc_id, "question": "x?"}).json()
    assert all(PAGE_SEPARATOR not in s["excerpt"] for s in body["sources"])
