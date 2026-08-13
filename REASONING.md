# Reasoning

Every number below was measured on the 200 listings actually in the database
(100 for sale, 100 to rent, Kraków, from nieruchomosci-online.pl), not estimated.

## The problem I chose

Every portal filters by **number of rooms**. That number answers almost nobody's
real question. Three flatmates need three rooms with doors: nobody wants to sleep
in the walk-through living room. A couple working from home needs a living area
*plus* separate rooms. Listings themselves conflate the two: "3 rooms" is
sometimes two bedrooms and a lounge, sometimes three independent rooms.

So this prototype searches by **how a flat can be lived in**: separate closable
bedrooms, and whether the kitchen is open to the living room.

The evidence that this is a real gap rather than a nice idea: the portal's
structured data **has** a `numberOfBedrooms` field, and it is empty in **200 out
of 200** listings. The field exists, but nobody fills it. The information is in the
prose of the description and nowhere else.

## Why Python for the core, TypeScript for the interface

The centre of gravity of this task is a data pipeline: fetch, parse messy HTML,
normalise, hand text to a language model, validate what comes back, store it. That
work is natively Python (`httpx`, `BeautifulSoup`, `SQLAlchemy`, `Pydantic`, the
Gemini SDK, `pytest`), and one language across it means no serialisation boundary
between scraping, normalisation and the API.

**The decisive argument is Pydantic**, because here one library does three jobs
that would otherwise be three artefacts. `SearchFilters` is the HTTP query
contract, the validation layer for language-model output, and via
`IntentFilters`, a strict subset of it the whitelist that makes a hallucinated
field name impossible. `Layout` goes **directly to the Gemini SDK** as the
structured-output schema, so the model's response shape and my validation are
literally the same declaration. A TypeScript backend would need a zod schema, a
separate JSON Schema for the model, and glue keeping them in sync.

The frontend is React and TypeScript because that is where TypeScript is the
natural choice, and because it is your stack. The honest cost of the split: a
TypeScript-first team gains real value from a single-language repository, shared
types across the wire, one toolchain, one CI and I traded that away for a core
written in the ecosystem the problem lives in.

## 1. What I extracted, and why

Price with a status (fixed / negotiable / unknown), area, raw room count, floor,
city, district, market, photos (the feature of a flat people actually remember),
coordinates, description, source URL: the fields people filter and browse by.

Then three that no structured field carries: **`bedrooms`** and **`open_kitchen`**,
the product's base, and **`monthly_fee`**, the building service charge, because a
tenant's budget is rent *plus* fees and the headline price hides that.

I also kept `page_title` in the raw records: the district lives there and nowhere
in the address object, and the phrase "z rynku pierwotnego" in it identifies
new-build listings.

## 2. Messy data

The interesting failures were semantic, not syntactic.

| What broke | Why | How it is handled |
| --- | --- | --- |
| District parsing, 21 listings | A decimal comma is also a comma: "Mieszkanie w Krakowie 64,70 m² z rynku pierwotnego" makes the naive last-comma rule return "70 m² z rynku pierwotnego" | Strip the known suffix first, then reject candidates containing digits |
| No city, 21% of listings | Exactly the developer ones leave `addressLocality` empty | Fallback chain: address → URL subdomain → page title |
| Wrong city, silently | Searching "Kraków" also returns Czarnochowice, a village outside it | City is normalised, never assumed from the query |
| Official district names | "Dzielnica XII Bieżanów-Prokocim (Bieżanów-Prokocim)" | Collapsed to the plain name |
| Uneven descriptions | Agency listings run 2,000–2,600 characters; new-build ones ~200 of generic copy | A natural ceiling on extraction, not a bug: short description → assumption used, record flagged low confidence |

Missing values are **flagged, not dropped**: a listing without a price is still a
listing. `raw_json` keeps the untouched source, so normalisation can be fixed
without re-scraping.

**The result I am least proud of, and kept anyway:** I wrote a regex to pull
explicit bedroom counts out of descriptions. Measured against the listings where it
disagreed with the simple assumption, it was **wrong in both**, it read one floor
of a duplex, and a phrase describing only the unfinished rooms. I deleted it. A
clever heuristic that fails silently is worse than a plain one that admits
uncertainty.

## 3. Where AI is used, and where it deliberately is not

**At ingest**, on the description, producing JSON: bedrooms, kitchen layout, a
confidence flag, the building fee. **In the search box**, mapping a sentence onto
filters. Nowhere else, the search itself is plain SQL: cheap, testable, incapable
of hallucinating.

That is the one job SQL cannot do. One listing reads "a living room with kitchen,
two additional rooms, two bathrooms": two bedrooms, and the word "bedroom" never
appears. Another has a room-by-room breakdown contradicting the portal's own room
count, because the flat was remodelled.

Safety is structural, not prompt-based:

- the model returns JSON validated by a Pydantic schema, and for the search box
  that schema is a strict subset of the filter contract the UI already uses, so
  **the whitelist and the API contract are the same object**;
- validated output then passes sanity checks: bedrooms cannot exceed rooms, and a
  flat with 2+ rooms must have at least one bedroom. The second rule caught a real
  failure: an investment listing with no layout description, where the model
  returned 0 bedrooms for a 7-room flat and honestly marked it low confidence.

The free tier allows **20 requests per day per model**, so one request per listing
is impossible; listings go in batches and 200 of them cost 10 requests. Results are
written back into `data/raw.json`, so a reviewer gets AI-parsed data **without a
key**. Without one the pipeline still runs, degrades to the assumption, and says so
in the interface.

**Outcome: 189 of 200 layouts came from the model, 182 with high confidence.**

I deliberately did **not** use embeddings or RAG: at 200 listings they add
infrastructure and answer nothing a validated filter does not.

## 4. The key assumption

**One room in a listing is the living room**, so `bedrooms = rooms - 1` whenever
the description does not say otherwise. For a studio this gives zero, which is
right. Everything resolved this way is stored as low confidence and badged "Layout
estimated" in the interface.

How often it matters: the model disagreed with the assumption in **17% of listings**
(32 of the 189 it parsed). I hand-checked five; the model was right in four: it
read room-by-room breakdowns, a remodelled flat whose room count was stale, and a
duplex whose rooms span two floors.

## 5. Success metric

**Share of listings whose layout is confirmed by the description rather than
assumed**: currently **91%** (182 of 200). It is the honest proxy for whether the
core search dimension can be trusted; if it dropped, the bedroom filter would
quietly become a guess with a UI around it.

Two product-level numbers showing the idea pays off:

- Searching for two separate bedrooms surfaces **13 flats that a "3+ rooms" filter
  misses** (5 for sale, 8 to rent) and misses none it would have found. The gain is
  largest in the rental market: exactly where flatmates need doors.
- At a 4,000 PLN budget, comparing against rent alone returns **22 listings**;
  counting the building fee returns **16**. Six flats - 27% look affordable and are not.

## 6. Failure modes I accept

**The source's own metadata is sometimes internally inconsistent**: the database
holds a 10 m2 micro-studio the portal lists as having 3 rooms. Sanity checks
constrain bedrooms against rooms but never rooms against area, so the absurdity
propagates. A rule like "under 25 m2 means at most one room" would catch it; I left
it out rather than tune thresholds on 200 listings.

**Fee semantics vary.** Fees are shown *as stated*, never silently added. They
appear in 80 of 100 rentals (median 700 PLN, about a quarter of a typical rent),
and some listings bundle utilities into that number while others do not. Folding
them into one "total" by default would invent a figure the source does not support,
so it is an explicit, labelled choice in the filter panel.

**The free tiers are visible in the product.** The API instance sleeps after 15
minutes; the model has a daily quota. Neither breaks the app: the search box falls
back to keyword parsing and says so, but both are limits a user can hit.

## 7. With more time

Semantic search over descriptions; a room-count-versus-area sanity rule; address
geocoding and validation; scheduled re-crawling; a third layout dimension (how many
independent private zones a flat can be split into); auth and per-user rate
limiting; end-to-end tests.

---

## Working with an AI assistant

I built this with an AI assistant throughout: exploring the source data, writing
code, drafting this document. The rule I held to was that nothing ships because a
model suggested it, but because I checked it. Three times that changed the
outcome:

- **The bedroom regex** came out of that collaboration, looked sensible, and was
  deleted once measured against the listings where it disagreed with the plain
  assumption. It was wrong in both.
- **The model I planned to use had been retired** for new accounts. I found out by
  calling the API, not by trusting documentation or recollection and the
  replacement turned out to be nine times faster on this task.
- **The 20-requests-per-day quota** was discovered by hitting it, which is the only
  reason extraction is batched at all. A per-listing design would have looked fine
  in review and failed on the 21st listing.

The assistant made writing code faster. It did not relieve me of verifying claims,
and every number in this document is the output of something I ran.

## What I deliberately did not build

Scoping decisions are decisions, so they belong here.

| Not built | Why |
| --- | --- |
| DDD, aggregates, event sourcing, CQRS | At this size a layered structure with a repository and Pydantic contracts is enough; more would be ceremony |
| A migration tool | The database is fully reproducible from a committed file, so schema changes recreate the table a defensible trade *only because* the data is reproducible |
| An interactive map | Coordinates exist for 179 of 200 listings, so the detail page links to OpenStreetMap rather than pulling in a mapping library and tile server for a demo |
| Embeddings / RAG | Nothing at this scale that a validated filter does not already answer |

And one worth stating plainly: **I did not expose the scraper as an endpoint.** The
ingest is deliberately re-runnable and idempotent, and a "fetch new listings"
button on the deployed site would have been easy. It would also have turned a demo
into an unauthenticated scraping service pointed at someone else's server,
triggerable by any stranger who found the URL. It stays a CLI script, run
deliberately by the project owner.

On scraping generally: the portal's `robots.txt` has no `User-agent: *` section at
all, only rules for Googlebot and bingbot, plus a blocklist of SEO crawlers.
Formally nothing there restricts this. I still kept a 1.5 s delay between requests
(bingbot is given `Crawl-delay: 1`), a realistic user agent, and a hard stop at
~100 listings per market. The scraper runs once; everything downstream reads a
committed file, so neither the demo nor the reviewers generate traffic on that site.

## On the API key

The key sits in `.env` locally and in the host's environment variables in
production, and is never sent to the browser: I verified that the deployed frontend
bundle contains no key material and that `.env` never entered git history. Intent
parsing lives in the backend for exactly that reason: calling an LLM from React
would publish the key to every visitor.

In a commercial system I would never ask a user for their own key; it is a company
secret held server-side in a secret manager, with auth, per-user rate limiting and
response caching against cost and abuse. None of that is implemented here, on
purpose, but the one decision that would be expensive to retrofit, keeping the
model call server-side, is already made.
