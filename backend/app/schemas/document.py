from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """What a client sees about a document.

    The storage location (file_path) is deliberately not exposed: originals
    are private and only the server can generate access to them.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    processing_status: str
    processing_error: Optional[str] = None
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
