import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, applications, assistant, audit, documents, feedback, integrations, ml, reports, review
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.logging_config import configure_logging
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.models import Reviewer
from app.services.workflow_service import IllegalTransitionError

settings = get_settings()
configure_logging(log_level=settings.log_level, environment=settings.app_env)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Environmental Scheme Application Intelligence Platform",
    description=(
        "Enterprise POC for the Directorate of Environment and Climate Change: "
        "ingests, extracts, validates, scores, and routes scheme applications, "
        "with a human reviewer always making the final determination."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(applications.router)
app.include_router(documents.router)
app.include_router(documents.doc_router)
app.include_router(review.router)
app.include_router(analytics.router)
app.include_router(assistant.router)
app.include_router(audit.router)
app.include_router(ml.router)
app.include_router(reports.router)
app.include_router(integrations.router)
app.include_router(feedback.router)


@app.exception_handler(IllegalTransitionError)
def illegal_transition_handler(request: Request, exc: IllegalTransitionError):
    logger.warning("Illegal state transition", extra={"detail": str(exc),
                   "path": request.url.path})
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", extra={"error": str(exc),
                 "path": request.url.path}, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        if db.query(Reviewer).count() == 0:
            for name, role in [
                ("A. Sharma", "Senior Reviewer"),
                ("P. Banerjee", "Reviewer"),
                ("R. Iyer", "Reviewer"),
            ]:
                db.add(Reviewer(name=name, role=role))
            db.commit()
            logger.info("Seeded default reviewers")
    finally:
        db.close()
    logger.info(
        "Application started",
        extra={"ai_provider": settings.ai_provider, "environment": settings.app_env},
    )


@app.get("/api/v1/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "ai_provider": settings.ai_provider,
        "environment": settings.app_env,
    }


@app.get("/", tags=["system"])
def root():
    return {
        "service": "eco-review-platform-backend",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
