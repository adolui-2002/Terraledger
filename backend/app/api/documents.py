from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app import schemas
from app.config import get_settings
from app.database import get_db
from app.models import Application, Document
from app.services import audit_service, extraction_service, language_service

router = APIRouter(prefix="/api/v1/applications", tags=["documents"])
doc_router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
settings = get_settings()


@router.post("/{application_id}/documents", response_model=schemas.DocumentOut, status_code=201)
async def upload_document(
    application_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "Application not found")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "Uploaded file is empty.")

    content_hash = extraction_service.content_hash(data)
    suffix = Path(file.filename or "upload").suffix.lower()

    raw_text, ocr_used, ocr_confidence = "", False, None
    try:
        if suffix == ".pdf":
            raw_text, needs_ocr = extraction_service.extract_pdf_text(data)
            ocr_used = needs_ocr
            if needs_ocr:
                ocr_confidence = 0.0  # scanned/corrupt PDF — flagged for manual review
        elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            raw_text, conf = extraction_service.extract_image_text(data)
            ocr_used = True
            ocr_confidence = conf
        elif suffix in (".xlsx", ".xlsm"):
            amounts = extraction_service.extract_xlsx_amounts(data)
            raw_text = " ".join(f"₹{a:,.0f}" for a in amounts)
        elif suffix in (".txt", ".csv"):
            raw_text = data.decode("utf-8", errors="ignore")
        else:
            raw_text = ""
    except Exception:
        # Never let a malformed file crash the pipeline — it is simply
        # recorded with no extracted text and flagged via low confidence.
        raw_text, ocr_used, ocr_confidence = "", True, 0.0

    lang_info = language_service.normalize_document_language(raw_text)

    storage_dir = Path(settings.document_storage_path) / application_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{content_hash[:12]}_{file.filename}"
    storage_path.write_bytes(data)

    document = Document(
        application_id=application_id,
        filename=file.filename or "upload",
        doc_type=doc_type,
        storage_path=str(storage_path),
        content_hash=content_hash,
        raw_text=raw_text,
        ocr_used=ocr_used,
        ocr_confidence=ocr_confidence,
        detected_language=lang_info["detected_language"],
    )
    db.add(document)
    audit_service.log(db, application_id, "system", "DOCUMENT_UPLOADED",
                       {"filename": document.filename, "doc_type": doc_type, "ocr_used": ocr_used})
    db.commit()
    db.refresh(document)
    return document


@router.get("/{application_id}/documents", response_model=list[schemas.DocumentOut])
def list_documents(application_id: str, db: Session = Depends(get_db)):
    return db.query(Document).filter(Document.application_id == application_id).all()


@doc_router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")

    if not document.storage_path:
        raise HTTPException(404, "No file is stored for this document")

    storage_path = Path(document.storage_path)
    if not storage_path.exists():
        raise HTTPException(404, "File not found on disk")

    suffix = storage_path.suffix.lower()
    MIME_TYPES = {
        ".pdf":  "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".txt":  "text/plain",
        ".csv":  "text/csv",
    }
    media_type = MIME_TYPES.get(suffix, "application/octet-stream")

    # PDFs and images open inline in the browser; everything else is a download
    INLINE_TYPES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".txt"}
    content_disposition = (
        f"inline; filename=\"{document.filename}\""
        if suffix in INLINE_TYPES
        else f"attachment; filename=\"{document.filename}\""
    )

    with open(storage_path, "rb") as f:
        content = f.read()

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition},
    )
