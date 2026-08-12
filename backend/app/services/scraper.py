"""Scraper for nieruchomosci-online.pl site"""

import re
import time
import json
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup


SOURCE = "nieruchomosci-online.pl"
SEARCH_URL = "https://www.nieruchomosci-online.pl/szukaj.html"
OFFER_URL_RE = re.compile(r"https://[a-z-]+\.nieruchomosci-online\.pl/[^\"`\s]+/\d+\.html")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9",
}

REQUEST_DELAY_S = 1.5
MAX_RETRIES = 3

TRANSACTIONS = {"sale": "sprzedaz", "rent": "wynajem"}

class ScrapeError(RuntimeError):
    pass


def _get(client: httpx.Client, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise ScrapeError(f"Could not download {url}: {last_error}")


def build_search_url(city: str, page: int, transaction: str = "sale") -> str:
    query = f"3,mieszkanie,{TRANSACTIONS[transaction]},,{quote(city)}"
    return f"{SEARCH_URL}?{query}" + (f"&p={page}" if page > 1 else "")

def extract_offer_urls(html: str) -> list[str]:
    seen: dict[str, None] = {}
    for url in OFFER_URL_RE.findall(html):
        seen.setdefault(url.split("?")[0], None)
    return list(seen)


def extract_ld_json(html:str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


def extract_description(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = (
            soup.select_one("div.estate-desc-more")
            or soup.select_one("div.estate-desc-less")
            or soup.select_one("#boxCustomDesc")
    )
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    text = node.get_text(" ", strip=True)
    return re.sub(r"[ \t\xa0]+", " ", text).strip()


def parse_offer_page(html: str, url: str, transaction: str = "sale") -> dict:
    blocks = extract_ld_json(html)
    apartment = next((b for b in blocks if b.get("@type") == "Apartment"), None)
    if apartment is None:
        raise ScrapeError("no field Apartment in ld+json")

    web_page = next((b for b in blocks if b.get("@type") == "WebPage"), {})

    return {
        "source": SOURCE,
        "source_url": url,
        "transaction_type": transaction,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": apartment.get("name"),
        "page_title": web_page.get("name"),
        "description": extract_description(html),
        "ld_json": apartment,
    }


def scrape(city: str, limit: int, transaction: str = "sale", max_pages: int = 10) -> list[dict]:
    records: list[dict] = []
    visited: set[str] = set()
    failures = 0

    with httpx.Client() as client:
        for page in range(1, max_pages + 1):
            if len(records) >= limit:
                break

            search_html = _get(client, build_search_url(city, page, transaction))
            offer_urls = [u for u in extract_offer_urls(search_html) if u not in visited]
            if not offer_urls:
                print(f"[scrape] page {page}: nothing new, ending")
                break

            print(f"[scrape] page {page}: {len(offer_urls)} ofers")
            for url in offer_urls:
                if len(records) >= limit:
                    break
                visited.add(url)
                time.sleep(REQUEST_DELAY_S)
                try:
                    records.append(parse_offer_page(_get(client, url), url, transaction))
                except ScrapeError as exc:
                    failures += 1
                    print(f"[scrape] skip {url}: {exc}")
                    continue
                print(f"[scrape] {len(records)}/{limit} {records[-1]['title']}")

            time.sleep(REQUEST_DELAY_S)

    print(f"[scrape] found {len(records)} ofers, skipped {failures}")
    return records