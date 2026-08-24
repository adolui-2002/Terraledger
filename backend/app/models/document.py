import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)

    filename: Mapped[str] = mapped_column(String)
    doc_type: Mapped[str] = mapped_column(String)  # DocumentType
    storage_path: Mapped[str] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, index=True, nullable=True)

    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    ocr_used: Mapped[bool] = mapped_column(default=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    detected_language: Mapped[str] = mapped_column(String, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="documents")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=True)

    field_name: Mapped[str] = mapped_column(String)
    field_value: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.9)

    application = relationship("Application", back_populates="extracted_fields")
