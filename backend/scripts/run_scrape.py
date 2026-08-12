from pathlib import Path
import argparse
import json

from app.services.scraper import TRANSACTIONS, scrape


DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "raw.json"

def main() -> None:
    parser = argparse.ArgumentParser(description="Pobiera oferty i zapisuje do raw.json")
    parser.add_argument("--city", default="Kraków")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--transaction", choices=sorted(TRANSACTIONS), default="sale")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--replace", action="store_true",
                        help="discard the existing file instead of merging into it")
    args = parser.parse_args()

    records = scrape(args.city, limit=args.count, transaction=args.transaction)
    if not records:
        raise SystemExit("no offers collected. leaving raw.json untouched")

    existing: list[dict] = []
    if args.out.exists() and not args.replace:
        existing = json.loads(args.out.read_text(encoding="utf-8"))

    merged = {record["source_url"]: record for record in existing}
    added = sum(1 for record in records if record["source_url"] not in merged)
    for record in records:
        if record["source_url"] not in merged:
            merged[record["source_url"]] = record

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(list(merged.values()), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    size_kb = args.out.stat().st_size / 1024
    print(
        f"[run_scrape] {args.transaction}: scraped {len(records)}, "
        f"new {added}, total {len(merged)} → {args.out} ({size_kb:.0f} KB)"
    )


if __name__ == "__main__":
    main()