import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, fetchCities, fetchListings } from "../api/client";
import { Filters } from "../components/Filters";
import { IntentSearch } from "../components/IntentSearch";
import { ListingCard } from "../components/ListingCard";
import { Pagination } from "../components/Pagination";
import type {
  Filters as FilterValues,
  ListingSummary,
  Market,
  Page,
  SortOption,
  TransactionType,
} from "../types";

const NUMERIC_KEYS = ["price_min", "price_max", "area_min", "area_max", "rooms_min", "bedrooms_min", "page"] as const;

function parseFilters(params: URLSearchParams): FilterValues {
  const filters: FilterValues = {};

  const transaction = params.get("transaction_type");
  filters.transaction_type = transaction === "rent" ? "rent" : "sale";

  const q = params.get("q");
  if (q) filters.q = q;
  const city = params.get("city");
  if (city) filters.city = city;
  const market = params.get("market");
  if (market) filters.market = market as Market;
  const sort = params.get("sort");
  if (sort) filters.sort = sort as SortOption;
  const openKitchen = params.get("open_kitchen");
  if (openKitchen !== null) filters.open_kitchen = openKitchen === "true";
  if (params.get("include_fees") === "true") filters.include_fees = true;

  for (const key of NUMERIC_KEYS) {
    const value = params.get(key);
    if (value !== null && value !== "" && !Number.isNaN(Number(value))) {
      filters[key] = Number(value);
    }
  }

  return filters;
}

function toParams(filters: FilterValues): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    // null matters as much as undefined here: the intent endpoint returns
    // explicit nulls for everything it did not set, and String(null) is "null",
    // which would end up in the URL as a literal search term
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  return params;
}

export function AllListingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);

  const [data, setData] = useState<Page<ListingSummary> | null>(null);
  const [cities, setCities] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const transaction: TransactionType = filters.transaction_type ?? "sale";

  useEffect(() => {
    fetchCities(transaction)
      .then(setCities)
      .catch(() => setCities([]));
  }, [transaction]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    fetchListings({ page_size: 12, ...filters })
      .then((page) => {
        if (active) setData(page);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(cause instanceof ApiError ? cause.message : "Something went wrong");
        setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filters]);

  const patch = useCallback(
    (changes: Partial<FilterValues>) => {
      setSearchParams(toParams({ ...filters, ...changes, page: undefined }));
    },
    [filters, setSearchParams],
  );

  const goToPage = useCallback(
    (page: number) => {
      setSearchParams(toParams({ ...filters, page }));
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [filters, setSearchParams],
  );

  const reset = useCallback(
    () => setSearchParams(toParams({ transaction_type: transaction })),
    [transaction, setSearchParams],
  );

  const applyIntent = useCallback(
    (next: FilterValues) => {
      setSearchParams(toParams({ ...next, page: undefined, page_size: undefined }));
    },
    [setSearchParams],
  );

  return (
    <div className="layout">
      <Filters
        values={filters}
        cities={cities}
        onChange={patch}
        onReset={reset}
      />

      <main className="results">
        <IntentSearch onFilters={applyIntent} />

        <header className="results-header">
          <h1>{transaction === "rent" ? "Apartments to rent" : "Apartments for sale"}</h1>
          {data && !loading && (
              <p className="results-count">
                {data.total === 0 ? "No listings match your criteria" : `${data.total} listings found`}
            </p>
          )}
        </header>

        {loading && <p className="state">Loading…</p>}

        {error && (
          <div className="state state-error" role="alert">
            <p>{error}</p>
          </div>
        )}

        {data && !loading && data.items.length === 0 && (
          <div className="state">
            <p>Try relaxing the filters — for example, lower the number of bedrooms.</p>
          </div>
        )}

        {data && !loading && data.items.length > 0 && (
          <>
            <div className="grid">
              {data.items.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
            <Pagination page={data.page} pages={data.pages} onChange={goToPage} />
          </>
        )}
      </main>
    </div>
  );
}