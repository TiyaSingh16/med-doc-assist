from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.ai.chains import ask_question
from app.utils.dependencies import get_current_user
from app.utils.logger import setup_logger

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
        result = ask_question(request.document_id, request.question)
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