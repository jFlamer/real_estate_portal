from __future__ import annotations

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

MODEL_TIMEOUT_S = 30
MAX_RETRIES = 4
MIN_INTERVAL_S = 4.0  #free tier Gemini Flash: 15 req/min

PROMPT = """Jesteś analitykiem ogłoszeń nieruchomości. Na podstawie opisu ustal układ mieszkania.

Definicje:
- bedrooms: liczba osobnych, zamykanych pomieszczeń nadających się na sypialnię.
  NIE licz salonu ani pokoju dziennego. Pokój przechodni się NIE liczy.
- open_kitchen: true, gdy kuchnia jest połączona z salonem (aneks kuchenny,
  salon z kuchnią). false, gdy kuchnia jest osobnym pomieszczeniem.
- confidence: "high" tylko gdy opis wprost opisuje układ pomieszczeń.
  "low", gdy zgadujesz z ogólników marketingowych.

Liczba pokoi z ogłoszenia: {rooms}
Opis oferty:
\"\"\"
{description}
\"\"\"

Zwróć wyłącznie JSON zgodny ze schematem."""


class Layout(BaseModel):
    bedrooms: int = Field(ge=0, le=10)
    open_kitchen: bool
    confidence: Literal["high", "low"]


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
    return {"bedrooms": bedrooms, "open_kitchen": kitchen, "layout_confidence": "low"}


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

    def parse(self, description: str, rooms: int | None) -> Layout | None:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Layout,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        prompt = PROMPT.format(rooms=rooms if rooms is not None else "nieznana",
                               description=description[:6000])

        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                response = self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config
                )
                parsed = response.parsed
                return parsed if isinstance(parsed, Layout) else Layout.model_validate_json(
                    response.text
                )
            except ValidationError as exc:
                logger.warning("LLM returned JSON mismatching the scheme: %s", exc)
                return None
            except errors.ClientError as exc:
                if exc.code != 429:
                    logger.error("Wrong query (%s), using heuristics", exc.code)
                    return None
                wait = 2 ** attempt
                logger.warning("Limit zapytań, ponawiam za %ss", wait)
                time.sleep(wait)
            except Exception as exc:
                wait = 2**attempt
                logger.warning("Gemini unreachable (%s), trying again in %ss", exc, wait)
                time.sleep(wait)
        return None


def is_plausible(layout: Layout, rooms: int | None) -> bool:
    if rooms is None:
        return True
    return layout.bedrooms <= rooms


def parse_layout(
    description: str,
    rooms: int | None,
    source_url: str | None = None,
    parser: GeminiLayoutParser | None = None,
) -> dict:
    if parser is not None and len(description or "") >= 300:
        layout = parser.parse(description, rooms)
        if layout is not None and is_plausible(layout, rooms):
            kitchen = kitchen_from_url(source_url)
            return {
                "bedrooms": layout.bedrooms,
                "open_kitchen": layout.open_kitchen if kitchen is None else kitchen,
                "layout_confidence": layout.confidence,
            }
        logger.info("LLM did not give reliable output, trying with heuristic")

    return heuristic_layout(description, rooms, source_url)


def build_llm_parser() -> GeminiLayoutParser | None:
    from app.config import settings

    if not settings.gemini_api_key:
        logger.info("no GEMINI_API_KEY -> heuristic approach")
        return None
    return GeminiLayoutParser(settings.gemini_api_key, settings.gemini_model)