from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.repositories import listing_repo
from app.schemas.listing import ListingDetail, ListingSummary, Page
from app.schemas.search import SearchFilters

router = APIRouter(prefix="/listings", tags=["listings"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=Page[ListingSummary], summary="Offers list with filters")
def list_listings(
    filters: Annotated[SearchFilters, Query()], session: SessionDep) -> Page[ListingSummary]:
    listings, total = listing_repo.search(session, filters)
    return Page[ListingSummary](
        items=[ListingSummary.model_validate(listing) for listing in listings],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        pages=ceil(total / filters.page_size) if total else 0,
    )


@router.get("/cities", response_model=list[str], summary="Cities in the database")
def list_cities(session: SessionDep, transaction_type: Literal["sale", "rent"] = "sale") -> list[str]:
    return listing_repo.distinct_cities(session, transaction_type)


@router.get("/{listing_id}", response_model=ListingDetail, summary="Ofers details")
def get_listing(listing_id: int, session: SessionDep) -> ListingDetail:
    listing = listing_repo.get(session, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="No such offer")
    return ListingDetail.model_validate(listing)