import argparse
import json
import logging
from collections import Counter
from pathlib import Path

from app.db.models import Base, Listing
from app.db.session import SessionLocal, engine
from app.repositories import listing_repo
from app.services.layout_parser import heuristic_layout
from app.services.normalizer import normalize

logger = logging.getLogger(__name__)

DEFAULT_RAW = Path(__file__).resolve().parent.parent / "data" / "raw.json"

LAYOUT_KEYS = ("bedrooms", "open_kitchen", "layout_confidence")


def build_row(record: dict) -> dict:
    row = normalize(record)

    layout = record.get("layout")
    if layout:
        row |= {key: layout.get(key) for key in LAYOUT_KEYS}
        row["layout_source"] = layout.get("parsed_by", "heuristic")
    else:
        row |= heuristic_layout(row["description"], row["rooms"], row["source_url"])
        row["layout_source"] = "heuristic"

    row["layout_confidence"] = row.get("layout_confidence") or "low"
    return row


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Loading raw.json to MySQL")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    args = parser.parse_args()

    records = json.loads(args.raw.read_text(encoding="utf-8"))
    rows = [build_row(record) for record in records]

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        added, updated = listing_repo.upsert_many(session, rows)
        total = listing_repo.count(session)

    sources = Counter(row["layout_source"] for row in rows)
    confidence = Counter(row["layout_confidence"] for row in rows)
    logger.info("added %d, actualised %d, in db %d", added, updated, total)
    logger.info("LLM layout: %d, heuristics: %d", sources["llm"], sources["heuristic"])
    logger.info("layout confidence: high %d, low %d", confidence["high"], confidence["low"])


if __name__ == '__main__':
    main()