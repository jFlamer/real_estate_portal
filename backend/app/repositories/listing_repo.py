from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from app.db.models import Listing


UPSERT_COLUMNS = (
    "source", "title", "description", "price", "price_status", "area", "rooms", "floor",
    "bedrooms", "open_kitchen", "layout_confidence", "layout_source",
    "city", "district", "market", "dedup_hash", "raw_json",
)


def upsert_many(session: Session, rows: list[dict]) -> tuple[int, int]:
    if not rows:
        return (0,0)

    urls = [row["source_url"] for row in rows]
    known = set(
        session.scalars(select(Listing.source_url).where(Listing.source_url.in_(urls))).all()
    )

    statement = insert(Listing).values(rows)
    updates = {column: statement.inserted[column] for column in UPSERT_COLUMNS}

    updates["updated_at"] = func.now()
    statement = statement.on_duplicate_key_update(updates)
    session.execute(statement)
    session.commit()

    updated = len(known)
    return (len(rows) - updated, updated)


def count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Listing)) or 0