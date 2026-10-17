from langchain_google_genai import ChatGoogleGenerativeAI

from app.ai.embedder import UNKNOWN_PAGE, ensure_vectors
from app.ai.prompts import MEDICAL_QA_PROMPT
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger()

TOP_K = 4
EXCERPT_PREVIEW_CHARS = 240


def get_llm(temperature: float = 0.3):
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )


def retrieve(document_id: str, extracted_text: str | None, question: str):
    """Top-k chunks for the question, rebuilding the index first if it was lost."""
    store = ensure_vectors(document_id, extracted_text)
    return store.as_retriever(search_kwargs={"k": TOP_K}).invoke(question)


def page_label(meta: dict) -> str:
    page = meta.get("page", UNKNOWN_PAGE)
    return str(page) if page and page != UNKNOWN_PAGE else "unknown"


def format_context(docs) -> str:
    # Each excerpt gets a header with its page, so the model can cite it.
    return "\n\n".join(
        f"[excerpt {i} | page {page_label(d.metadata)}]\n{d.page_content}" for i, d in enumerate(docs, start=1)
    )


def to_sources(docs) -> list[dict]:
    """What the UI shows under an answer, so a user can check it against the PDF."""
    return [
        {
            "excerpt_number": i,
            "page": d.metadata.get("page") or None,
            "chunk_index": d.metadata.get("chunk_index"),
            "excerpt": d.page_content[:EXCERPT_PREVIEW_CHARS],
        }
        for i, d in enumerate(docs, start=1)
    ]


def build_prompt(docs, question: str) -> str:
    return MEDICAL_QA_PROMPT.format(context=format_context(docs), question=question)


def ask_question(document_id: str, extracted_text: str | None, question: str) -> dict:
    """Retrieve once, answer from those chunks, and return them as sources.

    Before, the chain retrieved inside the pipeline and then called the
    retriever a second time just to count chunks (twice the work, and the
    count could describe different chunks than the answer used).
    """
    docs = retrieve(document_id, extracted_text, question)
    answer = get_llm().invoke(build_prompt(docs, question)).content
    logger.info(f"Question answered for doc {document_id}, used {len(docs)} chunks")
    return {"answer": answer, "chunks_used": len(docs), "sources": to_sources(docs)}


async def stream_answer(docs, question: str):
    """Yield answer tokens for already-retrieved chunks."""
    async for chunk in get_llm().astream(build_prompt(docs, question)):
        if chunk.content:
            yield chunk.content
