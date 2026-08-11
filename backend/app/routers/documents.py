import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.services.pdf_service import smart_extract, upload_to_cloudinary
from app.ai.embedder import embed_document
from app.utils.dependencies import get_current_user
from app.utils.logger import setup_logger
from app.services.extraction import extract_structured_data
from app.schemas.extraction import ExtractionResult
from app.services.comparison import compare_documents
from app.schemas.comparison import ComparisonResult
from pydantic import BaseModel

logger = setup_logger()
router = APIRouter(prefix="/documents", tags=["Documents"])


def process_document(document_id: str, file_path: str, db: Session):
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return
        extracted_text = smart_extract(file_path)
        document.extracted_text = extracted_text
        db.commit()
        embed_success = embed_document(extracted_text, document_id)
        if embed_success:
            document.processing_status = "completed"
        else:
            document.processing_status = "failed"
        db.commit()
        logger.info(f"Document processed successfully: {document_id}")
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.processing_status = "failed"
            db.commit()
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

class CompareRequest(BaseModel):
    document_id_a: str
    document_id_b: str
@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be under 10MB")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        file_url = upload_to_cloudinary(tmp_path, file.filename)

        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_url,
            processing_status="processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        background_tasks.add_task(
            process_document,
            str(document.id),
            tmp_path,
            db,
        )

        logger.info(f"Document uploaded: {file.filename} by user {current_user.email}")
        return DocumentResponse(
            id=str(document.id),
            filename=document.filename,
            processing_status=document.processing_status,
            created_at=document.created_at,
            file_path=document.file_path,
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/", response_model=DocumentListResponse)
async def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=str(doc.id),
                filename=doc.filename,
                processing_status=doc.processing_status,
                created_at=doc.created_at,
                file_path=doc.file_path,
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
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

    return DocumentResponse(
        id=str(document.id),
        filename=document.filename,
        processing_status=document.processing_status,
        created_at=document.created_at,
        file_path=document.file_path,
    )



@router.post("/{document_id}/extract", response_model=ExtractionResult)
async def extract_document_data(
    document_id: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.processing_status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for extraction (status: {document.processing_status})",
        )

    # Return cached result unless the user explicitly asks to re-run extraction
    if document.extracted_data and not force_refresh:
        logger.info(f"Returning cached extraction for document {document_id}")
        return ExtractionResult(**document.extracted_data)

    if not document.extracted_text:
        raise HTTPException(status_code=400, detail="No extracted text available for this document")

    try:
        result = extract_structured_data(document.extracted_text)
        document.extracted_data = result.model_dump()
        db.commit()
        logger.info(f"Extraction completed and cached for document {document_id}")
        return result
    except Exception as e:
        logger.error(f"Extraction endpoint failed for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Structured extraction failed")
def _get_or_extract(document: Document, db: Session) -> ExtractionResult:
    """
    Returns cached extraction if available, otherwise runs extraction and caches it.
    Shared helper so /compare reuses the same cache-first logic as /extract.
    """
    if document.extracted_data:
        return ExtractionResult(**document.extracted_data)

    if not document.extracted_text:
        raise HTTPException(
            status_code=400,
            detail=f"Document '{document.filename}' has no extracted text available",
        )

    result = extract_structured_data(document.extracted_text)
    document.extracted_data = result.model_dump()
    db.commit()
    return result


@router.post("/compare", response_model=ComparisonResult)
async def compare_two_documents(
    request: CompareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc_a = db.query(Document).filter(
        Document.id == request.document_id_a,
        Document.user_id == current_user.id,
    ).first()
    doc_b = db.query(Document).filter(
        Document.id == request.document_id_b,
        Document.user_id == current_user.id,
    ).first()

    if not doc_a or not doc_b:
        raise HTTPException(status_code=404, detail="One or both documents not found")

    for doc in (doc_a, doc_b):
        if doc.processing_status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Document '{doc.filename}' is not ready (status: {doc.processing_status})",
            )

    try:
        extraction_a = _get_or_extract(doc_a, db)
        extraction_b = _get_or_extract(doc_b, db)
        result = compare_documents(extraction_a, extraction_b)
        logger.info(f"Comparison completed between {doc_a.id} and {doc_b.id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=500, detail="Document comparison failed")