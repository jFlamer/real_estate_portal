from sqlalchemy import func, or_, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from app.db.models import Listing
from app.schemas.search import SearchFilters


UPSERT_COLUMNS = (
    "source", "transaction_type", "title", "description", "price", "price_status",
    "monthly_fee", "area", "rooms", "floor",
    "bedrooms", "open_kitchen", "layout_confidence", "layout_source",
    "city", "district", "market", "image_urls", "latitude", "longitude",
    "dedup_hash", "raw_json",
)

UPSERT_CHUNK = 50


def upsert_many(session: Session, rows: list[dict]) -> tuple[int, int]:
    if not rows:
        return (0, 0)

    urls = [row["source_url"] for row in rows]
    known = set(
        session.scalars(select(Listing.source_url).where(Listing.source_url.in_(urls))).all()
    )

    for start in range(0, len(rows), UPSERT_CHUNK):
        chunk = rows[start : start + UPSERT_CHUNK]
        statement = insert(Listing).values(chunk)
        updates = {column: statement.inserted[column] for column in UPSERT_COLUMNS}
        updates["updated_at"] = func.now()
        session.execute(statement.on_duplicate_key_update(updates))

    session.commit()

    updated = len(known)
    return (len(rows) - updated, updated)


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Listing)) or 0


def _price_column(filters: SearchFilters):
    if filters.include_fees and filters.transaction_type == "rent":
        return Listing.price + func.coalesce(Listing.monthly_fee, 0)
    return Listing.price


def _sort_clauses(filters: SearchFilters) -> tuple:
    price = _price_column(filters)
    return {
        "newest": (Listing.created_at.desc(),),
        "price_asc": (price.is_(None), price.asc()),
        "price_desc": (price.is_(None), price.desc()),
        "area_asc": (Listing.area.is_(None), Listing.area.asc()),
        "area_desc": (Listing.area.is_(None), Listing.area.desc()),
    }[filters.sort]


def _conditions(filters: SearchFilters) -> list:
    conditions = [Listing.transaction_type == filters.transaction_type]
    price = _price_column(filters)

    if filters.q:
        pattern = f"%{filters.q}%"
        conditions.append(or_(Listing.title.like(pattern), Listing.description.like(pattern)))
    if filters.city:
        conditions.append(Listing.city == filters.city)
    if filters.district:
        conditions.append(Listing.district == filters.district)
    if filters.price_min is not None:
        conditions.append(price >= filters.price_min)
    if filters.price_max is not None:
        conditions.append(price <= filters.price_max)
    if filters.area_min is not None:
        conditions.append(Listing.area >= filters.area_min)
    if filters.area_max is not None:
        conditions.append(Listing.area <= filters.area_max)
    if filters.rooms_min is not None:
        conditions.append(Listing.rooms >= filters.rooms_min)
    if filters.bedrooms_min is not None:
        conditions.append(Listing.bedrooms >= filters.bedrooms_min)
    if filters.open_kitchen is not None:
        conditions.append(Listing.open_kitchen.is_(filters.open_kitchen))
    if filters.market is not None:
        conditions.append(Listing.market == filters.market)

    return conditions


def search(session: Session, filters: SearchFilters) -> tuple[list[Listing], int]:
    conditions = _conditions(filters)

    total = session.scalar(
        select(func.count()).select_from(Listing).where(*conditions)
    ) or 0

    statement = (
        select(Listing)
        .where(*conditions)
        .order_by(*_sort_clauses(filters), Listing.id.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    return list(session.scalars(statement).all()), total


def get(session: Session, listing_id: int) -> Listing | None:
    return session.get(Listing, listing_id)


def distinct_cities(session: Session, transaction_type: str = "sale") -> list[str]:
    statement = select(Listing.city).where(Listing.city.is_not(None), Listing.transaction_type == transaction_type).distinct().order_by(Listing.city)
    return list(session.scalars(statement).all())