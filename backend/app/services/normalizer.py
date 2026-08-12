from __future__ import annotations

import hashlib
import re
from typing import Any

SUBDOMAIN_CITIES = {
    "krakow": "Kraków",
    "czarnochowice": "Czarnochowice",
    "warszawa": "Warszawa",
    "wroclaw": "Wrocław",
    "poznan": "Poznań",
    "gdansk": "Gdańsk",
    "lodz": "Łódź",
}

TITLE_NOISE = re.compile(r"\s*z rynku (pierwotnego|wtórnego)\s*$", re.I)
OFFICIAL_DISTRICT = re.compile(r"^Dzielnica\s+[IVXL]+\s+(?P<name>.+)$")
PARENTHETICAL = re.compile(r"^(?P<outer>[^(]+?)\s*\((?P<inner>[^)]+)\)$")

NEGOTIABLE = re.compile(r"do negocjacji|cena do negocjacji|negocjac", re.I)


def _first_offer(ld: dict) -> dict:
    offers = ld.get("offers") or []
    return offers[0] if offers else {}


def parse_price(ld: dict) -> int | None:
    raw = _first_offer(ld).get("price")
    if raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def detect_price_status(price: int | None, description: str) -> str:
    if price is None:
        return "unknown"
    return "negotiable" if NEGOTIABLE.search(description or "") else "fixed"


def parse_area(ld: dict) -> float | None:
    raw = ld.get("floorSize", {}).get("value")
    if raw is None:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", str(raw))
    return round(float(match.group().replace(",", ".")), 1) if match else None


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else None


def get_property(ld: dict, name: str) -> str | None:
    for prop in ld.get("additionalProperty", []):
        if prop.get("name") == name:
            value = str(prop.get("value", "")).strip()
            return value or None
    return None


def extract_city(record: dict) -> str | None:
    locality = (record.get("ld_json", {}).get("address", {}).get("addressLocality") or "").strip()
    if locality:
        return locality

    match = re.match(r"https://([a-z-]+)\.", record.get("source_url", ""))
    if match:
        subdomain = match.group(1)
        if subdomain in SUBDOMAIN_CITIES:
            return SUBDOMAIN_CITIES[subdomain]

    match = re.search(r"\bw\s+(Krakowie|Warszawie|Wrocławiu|Poznaniu|Gdańsku|Łodzi)\b",
                      record.get("page_title") or "")
    if match:
        return {"Krakowie": "Kraków", "Warszawie": "Warszawa", "Wrocławiu": "Wrocław",
                "Poznaniu": "Poznań", "Gdańsku": "Gdańsk", "Łodzi": "Łódź"}[match.group(1)]
    return None


def extract_district(page_title: str | None, city: str | None) -> str | None:
    if not page_title:
        return None

    title = TITLE_NOISE.sub("", page_title).strip()
    if "," not in title:
        return None

    candidate = title.rsplit(",", 1)[1].strip()

    if city and candidate.endswith(city):
        candidate = candidate[: -len(city)].strip()

    if not candidate or re.search(r"\d|m²|\|", candidate):
        return None
    if not candidate[0].isupper():
        return None

    match = OFFICIAL_DISTRICT.match(candidate)
    if match:
        candidate = match.group("name").strip()
    match = PARENTHETICAL.match(candidate)
    if match:
        candidate = match.group("inner").strip()

    if not candidate or (city and candidate == city) or len(candidate) > 40:
        return None
    return candidate


def detect_market(record: dict) -> str:
    url = record.get("source_url", "")
    page_title = record.get("page_title") or ""
    if "/nowe-mieszkanie," in url or "rynku pierwotnego" in page_title:
        return "primary"
    if "rynku wtórnego" in page_title:
        return "secondary"
    return "secondary" if record.get("ld_json", {}).get("address", {}).get("streetAddress") else "unknown"


def make_dedup_hash(transaction: str, city: str | None, street: str | None, area: float | None, rooms: int | None, price: int | None) -> str:
    parts = [
        transaction,
        (city or "").strip().lower(),
        re.sub(r"\s+", " ", (street or "").strip().lower()),
        f"{area:.1f}" if area is not None else "",
        str(rooms or ""),
        str(price or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def parse_images(ld: dict) -> list[str]:
    """Zdjęcia oferty. Portal daje je jako listę URL-i; pojedynczy string też
    bywa poprawną wartością wg schema.org, więc przyjmujemy oba kształty."""
    raw = ld.get("image")
    if not raw:
        return []
    urls = raw if isinstance(raw, list) else [raw]
    return [url for url in urls if isinstance(url, str) and url.startswith("http")]


def parse_coordinates(ld: dict) -> tuple[float, float] | tuple[None, None]:
    """Współrzędne oferty; puste stringi (21 ofert deweloperskich) → brak."""
    geo = ld.get("geo") or {}
    try:
        return (float(geo.get("latitude")), float(geo.get("longitude")))
    except (TypeError, ValueError):
        return (None, None)


def normalize(record: dict) -> dict:
    ld = record.get("ld_json", {})
    address = ld.get("address", {})
    latitude, longitude = parse_coordinates(ld)

    price = parse_price(ld)
    area = parse_area(ld)
    rooms = parse_int(ld.get("numberOfRooms")) or parse_int(get_property(ld, "Number of rooms"))
    city = extract_city(record)
    description = record.get("description") or ""
    transaction = record.get("transaction_type") or "sale"

    return {
        "source": record.get("source"),
        "source_url": record.get("source_url"),
        "transaction_type": transaction,
        "title": record.get("title"),
        "description": description,
        "price": price,
        "price_status": detect_price_status(price, description),
        "area": area,
        "rooms": rooms,
        "floor": parse_int(get_property(ld, "Floor level")),
        "city": city,
        "district": extract_district(record.get("page_title"), city),
        "market": detect_market(record),
        "image_urls": parse_images(ld),
        "latitude": latitude,
        "longitude": longitude,
        "dedup_hash": make_dedup_hash(transaction, city, address.get("streetAddress"), area, rooms, price),
        "raw_json": record,
    }