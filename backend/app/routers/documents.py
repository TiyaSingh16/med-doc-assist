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