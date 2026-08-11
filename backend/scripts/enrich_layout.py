import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.services.layout_parser import (
    BATCH_SIZE,
    MIN_DESCRIPTION_CHARS,
    build_llm_parser,
    heuristic_layout,
    is_plausible,
    merge_layout,
    DailyQuotaExhausted,
)

logger = logging.getLogger(__name__)

DEFAULT_RAW = Path(__file__).resolve().parent.parent / "data" / "raw.json"


def _stamp(layout: dict, parsed_by: str) -> dict:
    return layout | {
        "parsed_by": parsed_by,
        "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args_parser = argparse.ArgumentParser(description="Enriches raw.json with LLM given layout")
    args_parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    args_parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args_parser.add_argument("--force", action="store_true", help="recalibrate also on enriched")
    args = args_parser.parse_args()

    llm = build_llm_parser()
    if llm is None:
        raise SystemExit(
            "No GEMINI_API_KEY in .env.\n"
            "Without key skip: seed uses heuristics"
        )

    records = json.loads(args.raw.read_text(encoding="utf-8"))

    todo: list[int] = []
    for index, record in enumerate(records):
        if record.get("layout") and not args.force:
            continue
        description = record.get("description") or ""
        rooms = record.get("ld_json", {}).get("numberOfRooms")
        if len(description) < MIN_DESCRIPTION_CHARS:
            record["layout"] = _stamp(
                heuristic_layout(description, rooms, record.get("source_url")), "heuristic"
            )
            continue
        todo.append(index)

    logger.info(
        "to be processed by LLM: %d ofers in %d queries",
        len(todo), -(-len(todo) // args.batch_size),
    )

    from_llm = fallback = 0
    for start in range(0, len(todo), args.batch_size):
        chunk = todo[start : start + args.batch_size]
        offers = [
            {
                "index": index,
                "rooms": records[index].get("ld_json", {}).get("numberOfRooms"),
                "description": records[index].get("description") or "",
            }
            for index in chunk
        ]

        try:
            results = llm.parse_batch(offers)
        except DailyQuotaExhausted:
            logger.error(
                "\ndaily API limit reached"
            )
            break

        if results is None:
            logger.warning("batch %d-%d failed, will be run again", chunk[0], chunk[-1])
            continue

        for index in chunk:
            record = records[index]
            rooms = record.get("ld_json", {}).get("numberOfRooms")
            layout = results.get(index)
            if layout is not None and is_plausible(layout, rooms):
                record["layout"] = _stamp(merge_layout(layout, record.get("source_url")), "llm")
                from_llm += 1
            else:
                record["layout"] = _stamp(
                    heuristic_layout(record.get("description") or "", rooms, record.get("source_url")),
                    "heuristic",
                )
                fallback += 1

        args.raw.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("batch %d-%d ready (with LLM: %d, fallback: %d)",
                    chunk[0], chunk[-1], from_llm, fallback)

    remaining = sum(1 for record in records if not record.get("layout"))
    logger.info("\nLLM layouot: %d, with heuristics: %d, left to process: %d",
                from_llm, fallback, remaining)

if __name__ == "__main__":
    main()