import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


from app.api import listings

app = FastAPI(title="Smart RE Listings API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router)


logger = logging.getLogger(__name__)


@app.exception_handler(OperationalError)
def handle_db_down(request: Request, exc: OperationalError) -> JSONResponse:
    ("Database unreachable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Check if MySQL contener is running"},
    )

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}