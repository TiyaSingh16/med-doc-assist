from functools import lru_cache

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.services.pdf_service import PAGE_SEPARATOR
from app.utils.logger import setup_logger

logger = setup_logger()

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
UNKNOWN_PAGE = 0  # Chroma metadata can't be None; 0 = page not known (old documents)


@lru_cache(maxsize=1)
def get_embeddings():
    """Load the embedding model once per process.

    Before, a new HuggingFaceEmbeddings (and the model weights) was created on
    every upload and every question. The import is also deferred, so code that
    never embeds (and the tests) does not need torch loaded.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    logger.info(f"Loading embedding model {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def collection_name(document_id: str) -> str:
    return f"doc_{document_id}"


def get_vectorstore(document_id: str) -> Chroma:
    return Chroma(
        collection_name=collection_name(document_id),
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_path,
    )


def split_into_chunks(text: str) -> list[tuple[str, dict]]:
    """Split text into chunks tagged with page number and position.

    Text extracted by this version has pages separated by a form feed, so each
    chunk knows its page. Older documents have no separators; their chunks
    get UNKNOWN_PAGE.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "],
    )
    pages = text.split(PAGE_SEPARATOR)
    has_pages = len(pages) > 1
    chunks = []
    for page_number, page_text in enumerate(pages, start=1):
        for piece in splitter.split_text(page_text):
            chunks.append((piece, {"page": page_number if has_pages else UNKNOWN_PAGE}))
    for index, (_, meta) in enumerate(chunks):
        meta["chunk_index"] = index
    return chunks


def embed_document(text: str, document_id: str) -> int:
    """(Re)build the document's vectors. Idempotent: replaces any existing ones.

    Returns the number of chunks stored. Raises on failure, so the caller can
    record why processing failed.
    """
    chunks = split_into_chunks(text)
    if not chunks:
        raise ValueError("no text to embed")
    store = get_vectorstore(document_id)
    store.reset_collection()  # re-embedding must not duplicate chunks
    store.add_texts(
        texts=[c for c, _ in chunks],
        metadatas=[{**m, "document_id": document_id} for _, m in chunks],
        ids=[f"{document_id}-{m['chunk_index']}" for _, m in chunks],
    )
    logger.info(f"Embedded document {document_id}: {len(chunks)} chunks")
    return len(chunks)


def ensure_vectors(document_id: str, extracted_text: str | None) -> Chroma:
    """Return the document's vector store, rebuilding it if it is missing.

    Chroma lives on the container's disk. On hosts like Railway that disk is
    replaced on every redeploy, so vectors vanish while PostgreSQL still says
    the document is "completed". The extracted text is safely in PostgreSQL,
    so instead of failing, rebuild the vectors from it on first use (the same
    self-healing idea as a reconciler: the database is the source of truth,
    the vector store is a derived cache).
    """
    store = get_vectorstore(document_id)
    if store._collection.count() == 0:
        if not extracted_text:
            raise ValueError("document has no extracted text to index")
        logger.warning(f"Vectors missing for document {document_id}; rebuilding from saved text")
        embed_document(extracted_text, document_id)
        store = get_vectorstore(document_id)
    return store
