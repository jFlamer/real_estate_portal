from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import listings

app = FastAPI(title="Smart RE Listings API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}