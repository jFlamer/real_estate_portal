import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api import listings
from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="TenantBestie API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router)


@app.exception_handler(OperationalError)
def handle_db_down(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error("Database unreachable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is unavailable. Please try again in a moment."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
