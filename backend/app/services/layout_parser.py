from __future__ import annotations

import json
import logging
import re
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

KITCHEN_SLUGS = {
    "z-aneksem-kuchennym": True,
    "z-oddzielna-kuchnia": False,
    "z-kuchnia-z-oknem": False,
}

OPEN_KITCHEN_RE = re.compile(r"aneks\w*\s+kuchen|kuchni\w*\s+otwart|salon\w*\s+z\s+kuchni", re.I)
CLOSED_KITCHEN_RE = re.compile(r"oddzieln\w+\s+kuchni|osobn\w+\s+kuchni|kuchni\w*\s+zamkni", re.I)

# podbij przy każdej zmianie kontraktu ekstrakcji — enrich przeliczy wtedy
# oferty zapisane starszą wersją, zamiast je pomijać jako „już gotowe"
LAYOUT_SCHEMA_VERSION = 2

MIN_DESCRIPTION_CHARS = 300
MAX_DESCRIPTION_CHARS = 4000
BATCH_SIZE = 10
MAX_RETRIES = 4
MIN_INTERVAL_S = 5.

PROMPT = """Jesteś analitykiem ogłoszeń nieruchomości. Dla KAŻDEJ oferty poniżej ustal układ mieszkania.

Definicje:
- bedrooms: liczba osobnych, zamykanych pomieszczeń nadających się na sypialnię.
  NIE licz salonu ani pokoju dziennego. Pokój przechodni się NIE liczy.
  Uwaga na mieszkania dwupoziomowe — zsumuj pokoje ze wszystkich poziomów.
- open_kitchen: true, gdy kuchnia jest połączona z salonem (aneks kuchenny,
  salon z kuchnią). false, gdy kuchnia jest osobnym pomieszczeniem.
- confidence: "high" tylko gdy opis wprost opisuje układ pomieszczeń.
  "low", gdy zgadujesz z ogólników marketingowych.
- monthly_fee: stała miesięczna opłata podana W OPISIE obok ceny — czynsz
  administracyjny do spółdzielni lub wspólnoty, także gdy ogłoszenie łączy go
  z mediami. Podaj samą liczbę w złotych.
  null, gdy opis nie podaje żadnej kwoty. NIE licz kaucji ani ceny najmu.
  NIE szacuj i NIE przeliczaj z metrażu — brak danych to null.

Zwróć dokładnie po jednym wyniku na ofertę, z zachowaniem numeru `index`.

{offers}"""

OFFER_TEMPLATE = """--- OFERTA index={index} (liczba pokoi z ogłoszenia: {rooms}) ---
{description}"""


class Layout(BaseModel):
    index: int
    bedrooms: int = Field(ge=0, le=10)
    open_kitchen: bool
    confidence: Literal["high", "low"]
    # None, gdy ogłoszenie nie podaje kwoty — wtedy UI mówi „nie podano"
    # zamiast sugerować, że opłat nie ma
    monthly_fee: int | None = Field(default=None, ge=0, le=20_000)


class DailyQuotaExhausted(RuntimeError):
    """Wyczerpany DOBOWY limit zapytań — ponawianie w tym przebiegu nie ma sensu."""


def kitchen_from_url(source_url: str | None) -> bool | None:
    if not source_url:
        return None
    match = re.search(r"\.pl/([^/]+)/\d+\.html", source_url)
    if not match:
        return None
    for part in match.group(1).split(","):
        if part in KITCHEN_SLUGS:
            return KITCHEN_SLUGS[part]
    return None


def heuristic_layout(description: str, rooms: int | None, source_url: str | None = None) -> dict:
    kitchen = kitchen_from_url(source_url)
    if kitchen is None and description:
        if OPEN_KITCHEN_RE.search(description):
            kitchen = True
        elif CLOSED_KITCHEN_RE.search(description):
            kitchen = False

    bedrooms = max(rooms - 1, 0) if rooms is not None else None
    # opłat administracyjnych nie da się wyliczyć z niczego — bez LLM zostaje brak
    return {
        "bedrooms": bedrooms,
        "open_kitchen": kitchen,
        "layout_confidence": "low",
        "monthly_fee": None,
    }


def is_plausible(layout: Layout, rooms: int | None) -> bool:
    if rooms is None:
        return True
    if layout.bedrooms > rooms:
        return False
    return not (rooms >= 2 and layout.bedrooms == 0)


def merge_layout(layout: Layout, source_url: str | None) -> dict:
    kitchen = kitchen_from_url(source_url)
    return {
        "bedrooms": layout.bedrooms,
        "open_kitchen": layout.open_kitchen if kitchen is None else kitchen,
        "layout_confidence": layout.confidence,
        "monthly_fee": layout.monthly_fee,
    }


def _to_layouts(parsed: object, text: str | None) -> dict[int, Layout]:
    if parsed is None and text:
        parsed = json.loads(text)

    if isinstance(parsed, dict):
        parsed = parsed.get("items", parsed)
    if isinstance(parsed, (Layout, dict)):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValidationError.from_exception_data("Layout", [])

    layouts = [item if isinstance(item, Layout) else Layout.model_validate(item) for item in parsed]
    return {item.index: item for item in layouts}


def _is_daily_quota(exc: Exception) -> bool:
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return False
    for detail in details.get("error", {}).get("details", []):
        for violation in detail.get("violations", []) or []:
            if "PerDay" in str(violation.get("quotaId", "")):
                return True
    return False


class GeminiLayoutParser:
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash") -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._last_call = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < MIN_INTERVAL_S:
            time.sleep(MIN_INTERVAL_S - elapsed)
        self._last_call = time.monotonic()

    def parse_batch(self, offers: list[dict]) -> dict[int,Layout] | None:
        from google.genai import errors, types

        if not offers:
            return {}

        blocks = "\n\n".join(
            OFFER_TEMPLATE.format(
                index=offer["index"],
                rooms=offer.get("rooms") if offer.get("rooms") is not None else "nieznana",
                description=(offer.get("description") or "")[:MAX_DESCRIPTION_CHARS],
            )
            for offer in offers
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[Layout],
            temperature=0.0,
        )

        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                response = self._client.models.generate_content(
                    model=self._model, contents=PROMPT.format(offers=blocks), config=config
                )
                return _to_layouts(response.parsed, response.text)
            except ValidationError as exc:
                logger.warning("LLM returned JSON mismatching the scheme: %s", exc)
                return None
            except errors.ClientError as exc:
                if exc.code != 429:
                    logger.error("Wrong query (%s), using heuristics", exc.code)
                    return None
                if _is_daily_quota(exc):
                    raise DailyQuotaExhausted from exc
                wait = 2 ** attempt * 10
                logger.warning("To many requests, trying again in %ss", wait)
                time.sleep(wait)
            except Exception as exc:
                wait = 2**attempt
                logger.warning("Gemini unreachable (%s), trying again in %ss", exc, wait)
                time.sleep(wait)
        return None


def build_llm_parser() -> GeminiLayoutParser | None:
    from app.config import settings

    if not settings.gemini_api_key:
        logger.info("no GEMINI_API_KEY -> heuristic approach")
        return None
    return GeminiLayoutParser(settings.gemini_api_key, settings.gemini_model)