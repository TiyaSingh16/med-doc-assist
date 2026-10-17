import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.chains import ask_question, retrieve, stream_answer, to_sources
from app.database import SessionLocal, get_db
from app.models.chat_message import ChatMessage
from app.models.document import Document
from app.models.user import User
from app.routers.documents import get_owned_document
from app.utils.dependencies import get_current_user
from app.utils.logger import setup_logger
from app.utils.rate_limit import limit_llm_calls

logger = setup_logger()
router = APIRouter(prefix="/chat", tags=["Chat"])

ANSWER_FAILED = "Sorry, I couldn't answer that right now. Please try again in a moment."


class QuestionRequest(BaseModel):
    document_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    excerpt_number: int
    page: Optional[int] = None
    chunk_index: Optional[int] = None
    excerpt: str


class AnswerResponse(BaseModel):
    answer: str
    document_id: str
    question: str
    chunks_used: int
    sources: List[Source] = []


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    chunks_used: int | None = None
    sources: List[Source] | None = None
    created_at: str


def _ready_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = get_owned_document(db, document_id, user)
    if document.processing_status != "completed":
        raise HTTPException(status_code=400, detail=f"Document is still {document.processing_status}")
    return document


def _save_message(document_id, user_id, role, content, chunks_used=None, sources=None) -> None:
    """Writes with a fresh session, so it is safe from the streaming generator,
    which keeps running after the request's own session has been closed."""
    db = SessionLocal()
    try:
        db.add(
            ChatMessage(
                document_id=document_id,
                user_id=user_id,
                role=role,
                content=content,
                chunks_used=None if chunks_used is None else str(chunks_used),
                sources=sources,
            )
        )
        db.commit()
    finally:
        db.close()


# Plain `def`: retrieval and the Gemini call are blocking, so FastAPI runs this
# in a worker thread instead of blocking the event loop for everyone.
@router.post("/query", response_model=AnswerResponse)
def query_document(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(limit_llm_calls),
):
    document = _ready_document(db, request.document_id, current_user)
    _save_message(document.id, current_user.id, "user", request.question)
    try:
        result = ask_question(str(document.id), document.extracted_text, request.question)
    except Exception:
        logger.exception(f"Chat query failed for document {document.id}")
        raise HTTPException(status_code=502, detail=ANSWER_FAILED)
    _save_message(document.id, current_user.id, "assistant", result["answer"], result["chunks_used"], result["sources"])
    return AnswerResponse(
        answer=result["answer"],
        document_id=str(document.id),
        question=request.question,
        chunks_used=result["chunks_used"],
        sources=result["sources"],
    )


@router.get("/{document_id}/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_document(db, document_id, current_user)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.document_id == document_id, ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [
        ChatMessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            chunks_used=int(m.chunks_used) if m.chunks_used else None,
            sources=m.sources,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/query/stream")
def query_document_stream(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(limit_llm_calls),
):
    # Validation happens before streaming starts, so errors are normal HTTP
    # status codes rather than events inside a 200 stream.
    document = _ready_document(db, request.document_id, current_user)
    document_id, extracted_text, user_id = document.id, document.extracted_text, current_user.id
    _save_message(document_id, user_id, "user", request.question)

    async def event_generator():
        full_answer = ""
        try:
            # Retrieval (and a possible index rebuild) is blocking work.
            docs = await run_in_threadpool(retrieve, str(document_id), extracted_text, request.question)
            async for token in stream_answer(docs, request.question):
                full_answer += token
                yield _sse({"type": "token", "content": token})
            sources = to_sources(docs)
            yield _sse({"type": "done", "chunks_used": len(docs), "sources": sources})
            await run_in_threadpool(_save_message, document_id, user_id, "assistant", full_answer, len(docs), sources)
            logger.info(f"Streamed answer saved for doc {document_id}")
        except Exception:
            logger.exception(f"Streaming chat failed for document {document_id}")
            yield _sse({"type": "error", "content": ANSWER_FAILED})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
