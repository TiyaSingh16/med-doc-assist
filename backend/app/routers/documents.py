import os
import tempfile
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.embedder import embed_document
from app.config import settings
from app.database import SessionLocal, get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.comparison import ComparisonResult
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.extraction import ExtractionResult
from app.services.comparison import compare_documents
from app.services.extraction import extract_structured_data
from app.services.pdf_service import ExtractionError, looks_like_pdf, smart_extract, upload_to_cloudinary
from app.utils.dependencies import get_current_user
from app.utils.logger import setup_logger
from app.utils.rate_limit import limit_llm_calls

logger = setup_logger()
router = APIRouter(prefix="/documents", tags=["Documents"])

# Routes are plain `def`, not `async def`, on purpose. They call blocking code
# (SQLAlchemy's synchronous session, Cloudinary, Gemini). Inside `async def`
# that blocks the event loop, so one slow Gemini call froze the whole server
# for every user. FastAPI runs `def` routes in a thread pool instead.

GENERIC_PROCESSING_ERROR = "Processing failed because of a server problem. Please try uploading the document again."


def to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        processing_status=doc.processing_status,
        processing_error=doc.processing_error,
        created_at=doc.created_at,
    )


def get_owned_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    """The document, only if it belongs to this user. 404 otherwise.

    Answering 404 (not 403) for someone else's document avoids confirming
    that the id exists.
    """
    document = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def process_document(document_id: str, file_path: str) -> None:
    """Background job: extract text, then embed it.

    Opens its own database session. The request's session belongs to the
    request and is closed when the response is sent; a background task must
    not keep using it.
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return
        try:
            document.extracted_text = smart_extract(file_path)
            db.commit()
            embed_document(document.extracted_text, document_id)
            document.processing_status = "completed"
            document.processing_error = None
        except ExtractionError as e:
            document.processing_status = "failed"
            document.processing_error = str(e)
        except Exception:
            logger.exception(f"Processing failed for document {document_id}")
            document.processing_status = "failed"
            document.processing_error = GENERIC_PROCESSING_ERROR
        db.commit()
        logger.info(f"Document {document_id} processed: {document.processing_status}")
    finally:
        db.close()
        if os.path.exists(file_path):
            os.remove(file_path)


class CompareRequest(BaseModel):
    document_id_a: uuid.UUID
    document_id_b: uuid.UUID


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Read at most one byte past the limit: enough to know the file is too big
    # without loading an arbitrarily large upload into memory.
    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File size must be under 10MB")
    if not looks_like_pdf(content):
        raise HTTPException(status_code=400, detail="The file is not a valid PDF")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        storage_key = upload_to_cloudinary(tmp_path, str(current_user.id))
        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=storage_key,
            processing_status="processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception:
        os.remove(tmp_path)
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Upload failed. Please try again.")

    background_tasks.add_task(process_document, str(document.id), tmp_path)
    logger.info(f"Document {document.id} uploaded by user {current_user.id}")
    return to_response(document)


@router.get("/", response_model=DocumentListResponse)
def get_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    documents = (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentListResponse(documents=[to_response(d) for d in documents], total=len(documents))


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return to_response(get_owned_document(db, document_id, current_user))


def _get_or_extract(document: Document, db: Session, force_refresh: bool = False) -> ExtractionResult:
    """Cached structured extraction; runs the LLM only when not cached (or forced)."""
    if document.extracted_data and not force_refresh:
        return ExtractionResult(**document.extracted_data)
    if not document.extracted_text:
        raise HTTPException(status_code=400, detail=f"Document '{document.filename}' has no extracted text available")
    result = extract_structured_data(document.extracted_text)
    document.extracted_data = result.model_dump()
    db.commit()
    return result


def _require_completed(document: Document) -> None:
    if document.processing_status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Document '{document.filename}' is not ready (status: {document.processing_status})",
        )


@router.post("/compare", response_model=ComparisonResult)
def compare_two_documents(
    request: CompareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(limit_llm_calls),
):
    doc_a = get_owned_document(db, request.document_id_a, current_user)
    doc_b = get_owned_document(db, request.document_id_b, current_user)
    for doc in (doc_a, doc_b):
        _require_completed(doc)
    try:
        result = compare_documents(_get_or_extract(doc_a, db), _get_or_extract(doc_b, db))
        logger.info(f"Comparison completed between {doc_a.id} and {doc_b.id}")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Comparison failed")
        raise HTTPException(status_code=502, detail="Document comparison failed. Please try again.")


@router.post("/{document_id}/extract", response_model=ExtractionResult)
def extract_document_data(
    document_id: uuid.UUID,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(limit_llm_calls),
):
    document = get_owned_document(db, document_id, current_user)
    _require_completed(document)
    try:
        return _get_or_extract(document, db, force_refresh=force_refresh)
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Extraction failed for document {document_id}")
        raise HTTPException(status_code=502, detail="Structured extraction failed. Please try again.")
