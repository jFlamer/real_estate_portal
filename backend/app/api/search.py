from __future__ import annotations

from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.repositories import listing_repo
from app.schemas.listing import ListingSummary, Page
from app.schemas.search import SearchFilters
from app.services.intent_parser import build_intent_parser, parse_intent

router = APIRouter(prefix="/search", tags=["search"])

SessionDep = Annotated[Session, Depends(get_session)]


class IntentRequest(BaseModel):
    query: str = Field(min_length=2, max_length=400)


class IntentResponse(BaseModel):
    filters: SearchFilters
    source: str = Field(description='"llm" or "keywords": which route produced the filters')
    results: Page[ListingSummary]


@router.post("/intent", response_model=IntentResponse, summary="Search by describing what you need")
def search_by_intent(payload: IntentRequest, session: SessionDep) -> IntentResponse:
    filters, source = parse_intent(payload.query, build_intent_parser())

    listings, total = listing_repo.search(session, filters)
    page = Page[ListingSummary](
        items=[ListingSummary.model_validate(listing) for listing in listings],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        pages=ceil(total / filters.page_size) if total else 0,
    )
    return IntentResponse(filters=filters, source=source, results=page)
