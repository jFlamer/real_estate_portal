from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.schemas.search import SearchFilters

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 400

PROMPT = """You turn a flat-hunter's sentence into search filters. Reply with JSON only.

Rules that matter more than literal wording:
- "cheap", "budget", "affordable" set sort to "price_asc". NEVER invent a price
  limit from such a word — you do not know the person's budget.
- A stated size like "around 40 m2" becomes a range (area_min 30, area_max 50),
  not an exact match.
- "own room each", "with a flatmate", "for a couple who both work from home",
  "two bedrooms" all set bedrooms_min. NEVER use rooms_min for these: a room
  count includes the living room, so it would seat somebody in the lounge.
- "rent", "renting", "monthly" set transaction_type "rent"; "buy", "purchase",
  "mortgage" set "sale". If nothing indicates it, leave it out.
- "including fees", "with the service charge", "all in" set include_fees true.
- An open-plan kitchen sets open_kitchen true; a separate kitchen sets it false.
- Leave a field out entirely when the sentence does not support it. Guessing is
  worse than an unset filter, because the user cannot see what they did not ask for.

User query:
\"\"\"{query}\"\"\"
"""

KNOWN_CITIES = ("Kraków", "Krakow", "Czarnochowice")

RENT_WORDS = re.compile(r"\b(rent|renting|wynaj|najem|monthly)\w*", re.I)
SALE_WORDS = re.compile(r"\b(buy|buying|purchase|sale|kupno|sprzeda)\w*", re.I)
CHEAP_WORDS = re.compile(r"\b(cheap|cheapest|budget|affordable|tani\w*)\b", re.I)
FEES_WORDS = re.compile(r"\b(with fees|including fees|all in|z czynszem)\b", re.I)
OPEN_KITCHEN_WORDS = re.compile(r"\b(open[- ]plan|open kitchen|aneks)\w*", re.I)
CLOSED_KITCHEN_WORDS = re.compile(r"\b(separate kitchen|closed kitchen|osobna kuchnia)\b", re.I)
BEDROOM_WORDS = re.compile(r"(\d+)\s*(?:separate\s+)?(?:bedroom|sypialni)\w*", re.I)
FLATMATE_WORDS = re.compile(r"\b(flatmate|roommate|housemate|wspó?llokator)\w*", re.I)
AREA_WORDS = re.compile(r"(\d{2,3})\s*(?:m2|m²|sqm|metr)\w*", re.I)
BUDGET_WORDS = re.compile(r"(?:under|below|up to|max|do)\s*(\d[\d\s,.]{2,8})", re.I)


class IntentFilters(BaseModel):
    transaction_type: Literal["sale", "rent"] | None = None
    city: str | None = Field(default=None, max_length=128)
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    include_fees: bool | None = None
    area_min: float | None = Field(default=None, ge=0)
    area_max: float | None = Field(default=None, ge=0)
    bedrooms_min: int | None = Field(default=None, ge=0, le=10)
    open_kitchen: bool | None = None
    sort: Literal["newest", "price_asc", "price_desc", "area_asc", "area_desc"] | None = None
    q: str | None = Field(default=None, max_length=200)


def to_search_filters(intent: IntentFilters) -> SearchFilters:
    values = intent.model_dump(exclude_none=True)
    if not values.get("transaction_type"):
        values["transaction_type"] = "sale"
    return SearchFilters(**values)


def keyword_intent(query: str) -> IntentFilters:
    intent = IntentFilters()

    if RENT_WORDS.search(query):
        intent.transaction_type = "rent"
    elif SALE_WORDS.search(query):
        intent.transaction_type = "sale"

    for city in KNOWN_CITIES:
        if city.lower() in query.lower():
            intent.city = "Kraków" if city.lower().startswith("krak") else city
            break

    if CHEAP_WORDS.search(query):
        intent.sort = "price_asc"

    if FEES_WORDS.search(query):
        intent.include_fees = True

    if OPEN_KITCHEN_WORDS.search(query):
        intent.open_kitchen = True
    elif CLOSED_KITCHEN_WORDS.search(query):
        intent.open_kitchen = False

    match = BEDROOM_WORDS.search(query)
    if match:
        intent.bedrooms_min = min(int(match.group(1)), 10)
    elif FLATMATE_WORDS.search(query):
        intent.bedrooms_min = 2

    match = AREA_WORDS.search(query)
    if match:
        area = int(match.group(1))
        intent.area_min = max(area - 10, 0)
        intent.area_max = area + 10

    match = BUDGET_WORDS.search(query)
    if match:
        digits = re.sub(r"[^\d]", "", match.group(1))
        if digits:
            intent.price_max = int(digits)

    return intent


def _normalise_city(city: str | None) -> str | None:
    if not city:
        return None
    stripped = city.strip().lower()
    for known in KNOWN_CITIES:
        if stripped == known.lower():
            return "Kraków" if stripped.startswith("krak") else known
    return city.strip()


def _apply_lexical_overrides(intent: IntentFilters, query: str) -> IntentFilters:
    if FEES_WORDS.search(query):
        intent.include_fees = True
    if OPEN_KITCHEN_WORDS.search(query):
        intent.open_kitchen = True
    elif CLOSED_KITCHEN_WORDS.search(query):
        intent.open_kitchen = False

    intent.city = _normalise_city(intent.city)
    return intent


def _sanity_check(intent: IntentFilters) -> IntentFilters:
    if intent.price_min and intent.price_max and intent.price_min > intent.price_max:
        intent.price_min, intent.price_max = None, intent.price_max
    if intent.area_min and intent.area_max and intent.area_min > intent.area_max:
        intent.area_min, intent.area_max = None, intent.area_max
    return intent


class GeminiIntentParser:
    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def parse(self, query: str) -> IntentFilters | None:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=PROMPT.format(query=query[:MAX_QUERY_CHARS]),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=IntentFilters,
                    temperature=0.0,
                ),
            )
            parsed = response.parsed
            if isinstance(parsed, IntentFilters):
                return parsed
            return IntentFilters.model_validate(json.loads(response.text))
        except ValidationError as exc:
            logger.warning("intent JSON did not validate: %s", exc)
            return None
        except Exception as exc:
            logger.warning("intent parsing unavailable (%s), falling back to keywords", exc)
            return None


def build_intent_parser() -> GeminiIntentParser | None:
    from app.config import settings

    if not settings.gemini_api_key:
        return None
    return GeminiIntentParser(settings.gemini_api_key, settings.gemini_model)


def parse_intent(query: str, parser: GeminiIntentParser | None) -> tuple[SearchFilters, str]:
    if parser is not None:
        intent = parser.parse(query)
        if intent is not None:
            intent = _apply_lexical_overrides(intent, query)
            return to_search_filters(_sanity_check(intent)), "llm"

    return to_search_filters(_sanity_check(keyword_intent(query))), "keywords"
