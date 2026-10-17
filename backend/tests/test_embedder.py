from app.ai import embedder
from app.ai.embedder import UNKNOWN_PAGE
from app.services.pdf_service import PAGE_SEPARATOR


def test_chunks_are_tagged_with_their_page():
    text = PAGE_SEPARATOR.join(["first page " * 80, "second page " * 80])
    chunks = embedder.split_into_chunks(text)
    pages = {meta["page"] for _, meta in chunks}
    assert pages == {1, 2}
    assert [m["chunk_index"] for _, m in chunks] == list(range(len(chunks)))


def test_old_documents_without_page_markers_get_unknown_page():
    chunks = embedder.split_into_chunks("no page markers here " * 40)
    assert {m["page"] for _, m in chunks} == {UNKNOWN_PAGE}


def test_re_embedding_replaces_instead_of_duplicating(fake_embeddings):
    text = "glucose " * 300
    n = embedder.embed_document(text, "doc-1")
    embedder.embed_document(text, "doc-1")
    assert embedder.get_vectorstore("doc-1")._collection.count() == n


def test_lost_vectors_are_rebuilt_from_saved_text(fake_embeddings):
    """Simulates a redeploy that wiped Chroma while Postgres still has the text."""
    text = "hemoglobin " * 300
    n = embedder.embed_document(text, "doc-2")
    embedder.get_vectorstore("doc-2").reset_collection()  # the "redeploy"
    assert embedder.get_vectorstore("doc-2")._collection.count() == 0

    store = embedder.ensure_vectors("doc-2", text)
    assert store._collection.count() == n


def test_existing_vectors_are_not_rebuilt(fake_embeddings, monkeypatch):
    embedder.embed_document("lipid panel " * 200, "doc-3")
    calls = []
    monkeypatch.setattr(embedder, "embed_document", lambda *a: calls.append(a))
    embedder.ensure_vectors("doc-3", "lipid panel " * 200)
    assert calls == []
