from pathlib import Path
import argparse
import json

from app.services.scraper import scrape


DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "raw.json"

def main() -> None:
    parser = argparse.ArgumentParser(description="Pobiera oferty i zapisuje do raw.json")
    parser.add_argument("--city", default="Kraków")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    records = scrape(args.city, limit=args.count)
    if not records:
        raise SystemExit("nie zebrano żadnej oferty — nie nadpisuję raw.json")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    size_kb = args.out.stat().st_size / 1024
    print(f"[run_scrape] zapisano {len(records)} ofert → {args.out} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()