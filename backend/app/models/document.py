from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=True)
    extracted_data = Column(JSONB, nullable=True)   # structured extraction result (cached)
    processing_status = Column(String, default="pending")
    processing_error = Column(Text, nullable=True)  # user-facing reason when status is "failed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())