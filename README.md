# TenantBestie

A listings prototype that searches flats by **how they can actually be lived in**,
the number of separate, closable bedrooms and whether the kitchen is open, rather
than by the raw room count every portal shows.

The portal this data comes from has a `numberOfBedrooms` field. It is empty in
200 out of 200 listings. That information exists only in the text of the
description, so an LLM extracts it once, at ingest.

**Live demo:** https://real-estate-portal-fe.onrender.com ·
**API docs:** https://real-estate-portal-f6y2.onrender.com/docs

The API runs on a free instance that sleeps after 15 minutes of inactivity, so
the first request after a pause takes 30–60 seconds. It is waking up, not broken.

### The decisions behind the project are in **[REASONING.md](REASONING.md)**.

## What it does

1. **Search by usable layout.** Filter by the number of separate, closable bedrooms
instead of the raw room count, and by whether the kitchen is open to the living
room. Both are extracted from the description by a language model, because the
portal's own `numberOfBedrooms` field is empty in all 200 listings.

2. **Two markets, never mixed.** Sale and rent live in one database but never share
a result list, a 2,600 PLN monthly rent and an 840,000 PLN asking price cannot
be sorted or bounded together. The Buy/Rent switch clears the price range when it
changes markets, and keeps the bedroom filter, which means the same thing in both.

3. **Honest rental budgets.** The building service charge is extracted from the
description where the listing states one (80 of 100 rentals, median 700 PLN) and
shown next to the rent, never folded into it silently. A checkbox decides whether
the budget filter compares against rent alone or rent plus fees.

4. **Free-text search.** Describe what you need in a sentence; a language model maps
it onto the same filters the panel exposes, and the panel visibly updates. The
filters are shown rather than applied invisibly, so a misreading can be corrected
with one click. Without an API key or once the daily quota is spent, a keyword
parser takes over and the UI says so.

5. **Visible data provenance.** Every listing states whether its layout was read
from the description by the model or estimated from the room count, and with what
confidence. Estimated layouts are badged in the results.

6. Also: photos and coordinates from the source listing, a link to the location on
OpenStreetMap, price per m², filters that live in the URL (so any search is a
shareable link and the back button behaves), and pagination.

## Example journeys

### A. Filters: a work from home couple buying in Kraków

[Kraków, 40–80 m², cheapest first](https://real-estate-portal-fe.onrender.com/?transaction_type=sale&city=Krak%C3%B3w&area_min=40&area_max=80&sort=price_asc)
→ 60 listings. Add **Separate bedrooms: 2+** and the list narrows to flats where
two people genuinely get a bedroom each plus a living room.

**The point of the journey:** switch that filter to the classic **rooms** instead.
For rentals, `2+ bedrooms` returns 41 listings while `3+ rooms` returns 33 — and
the 8 extra are two-room flats with two real bedrooms, exactly the ones a room
count hides. Open any of them and the description confirms it.

### B. Free text: two people renting together

Paste into the search box on the results page:

> renting with a flatmate, we each need our own bedroom, up to 4000 including fees

The line under the box shows what was understood: *to rent | 2+ separate
bedrooms | up to PLN 4,000 | fees included* and the filter panel on the left
fills in to match, so nothing happens invisibly.

The interesting part is the fee switch. With the same budget of 4,000 PLN,
comparing against rent alone returns **22 listings**; counting the building fee
returns **16**. Six flats look affordable and are not, which is the whole reason
the fee is extracted at all.

Other sentences worth trying:

> cheap flat to rent in Kraków with an open plan kitchen, around 40 m2

"Cheap" sets the sort order rather than inventing a price ceiling, and "around 40
m2" becomes a 30–50 range instead of an exact match.

## Run it locally (eg. developement)

Everything, with data already loaded, in one command:

```
docker compose up
```

Frontend on http://localhost:5173, API on http://localhost:8000, interactive API
docs on http://localhost:8000/docs.

No API key is needed. The 200 listings ship with the repository in
`backend/data/raw.json`, already enriched by the language model, and the backend
seeds the database from that file on every boot (the seed is an upsert, so
repeated runs are harmless).

### Development setup

```
docker compose up -d mysql
cd backend && uv sync && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Optional: copy `.env.example` to `.env` and add a Gemini key. It is only needed
to re-run the extraction pipeline, never to browse the app.

## What is where

```
backend/
  app/
    api/           HTTP layer, no SQL lives here
    services/      scraper, normalizer, layout_parser (the only LLM caller)
    repositories/  every database query
    schemas/       Pydantic contracts; also the whitelist for LLM-produced filters
    db/            SQLAlchemy models and session
  scripts/         run_scrape → enrich_layout → seed_db
  data/raw.json    scraped + enriched listings, committed on purpose
  tests/           104 tests, no network access
frontend/src/
  pages/           listing results and listing detail
  components/      filters, card, pagination
```

## The data pipeline

Three steps, each runnable on its own. Only the middle one needs an API key, and
its output is committed, so nobody else has to run it.

```
uv run python -m scripts.run_scrape --transaction rent --count 100
uv run python -m scripts.enrich_layout
uv run python -m scripts.seed_db
```

`run_scrape` merges into `raw.json` rather than overwriting it, so adding a second
market does not discard the first one's enrichment. `enrich_layout` sends listings
in batches (the free Gemini tier allows 20 requests per day, so one request per
listing is not an option), skips anything already parsed by the current schema
version, and stops cleanly when the daily quota runs out, rerunning it resumes.

## Deployment

The stack runs on free tiers: **Aiven** for MySQL and **Render** for the API
(Docker) and the frontend (static site).

| Service  | Setting |
| -------- | ------- |
| Aiven    | MySQL, Free plan. Copy the Service URI. |
| Render API | Web Service, root `backend`, runtime Docker, health check `/health`. |
| Render UI | Static Site, root `frontend`, build `npm ci && npm run build`, publish `dist`, rewrite `/*` → `/index.html`. |

Environment variables on the API service: `DATABASE_URL` (the Aiven URI: the
`mysql://…?ssl-mode=REQUIRED` form is handled), `CORS_ORIGINS` (the static site
URL), and optionally `GEMINI_API_KEY`. On the static site: `VITE_API_URL`
pointing at the API.

Two honest issues about the free tiers:

- The API instance **sleeps after 15 minutes of inactivity**, so the first request
  after a pause can take 30–60 seconds. It is not broken, it is waking up.
- The Gemini free tier allows **20 requests per day per model**. Browsing and
  filtering never call the model, only the chat does, and when the quota is gone
  it falls back to regex-based intent parsing instead of failing.

## Tests

```
cd backend && uv run pytest
```

104 tests covering the normalizer, the layout parser and the intent parser: price,
area, city and district parsing, deduplication, the room-count assumption, and the
validation and sanity checks applied to model output. Nothing touches the network,
so they run without a key and without a database.
