import json
from fastapi.responses import StreamingResponse
from app.ai.chains import ask_question_stream
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.ai.chains import ask_question
from app.utils.dependencies import get_current_user
from app.utils.logger import setup_logger
from typing import List
from app.models.chat_message import ChatMessage
logger = setup_logger()
router = APIRouter(prefix="/chat", tags=["Chat"])


class QuestionRequest(BaseModel):
    document_id: str
    question: str


class AnswerResponse(BaseModel):
    answer: str
    document_id: str
    question: str
    chunks_used: int

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    chunks_used: int | None = None
    created_at: str

    class Config:
        from_attributes = True

@router.post("/query", response_model=AnswerResponse)
async def query_document(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(
        Document.id == request.document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.processing_status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is still {document.processing_status}"
        )

    try:
        # Save the user's question
        user_message = ChatMessage(
            document_id=request.document_id,
            user_id=current_user.id,
            role="user",
            content=request.question,
        )
        db.add(user_message)
        db.commit()

        result = ask_question(request.document_id, request.question)

        # Save the assistant's answer
        assistant_message = ChatMessage(
            document_id=request.document_id,
            user_id=current_user.id,
            role="assistant",
            content=result["answer"],
            chunks_used=str(result["chunks_used"]),
        )
        db.add(assistant_message)
        db.commit()

        logger.info(
            f"Question answered for doc {request.document_id} "
            f"by user {current_user.email}"
        )
        return AnswerResponse(
            answer=result["answer"],
            document_id=request.document_id,
            question=request.question,
            chunks_used=result["chunks_used"],
        )
    except Exception as e:
        logger.error(f"Chat query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")
@router.get("/{document_id}/history", response_model=List[ChatMessageResponse])
async def get_chat_history(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.document_id == document_id,
            ChatMessage.user_id == current_user.id,
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return [
        ChatMessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            chunks_used=int(m.chunks_used) if m.chunks_used else None,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]
@router.post("/query/stream")
async def query_document_stream(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(
        Document.id == request.document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.processing_status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is still {document.processing_status}"
        )

    # Save the user's question before streaming starts
    user_message = ChatMessage(
        document_id=request.document_id,
        user_id=current_user.id,
        role="user",
        content=request.question,
    )
    db.add(user_message)
    db.commit()

    async def event_generator():
        full_answer = ""
        chunks_used = 0
        try:
            async for event in ask_question_stream(request.document_id, request.question):
                if event["type"] == "token":
                    full_answer += event["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
                elif event["type"] == "done":
                    chunks_used = event["chunks_used"]
                    yield f"data: {json.dumps({'type': 'done', 'chunks_used': chunks_used})}\n\n"

            # Save the assistant's full answer once streaming completes
            assistant_message = ChatMessage(
                document_id=request.document_id,
                user_id=current_user.id,
                role="assistant",
                content=full_answer,
                chunks_used=str(chunks_used),
            )
            db.add(assistant_message)
            db.commit()
            logger.info(f"Streamed answer saved for doc {request.document_id}")

        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to process question'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")