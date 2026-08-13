import type {
  Filters,
  IntentResponse,
  ListingDetail,
  ListingSummary,
  Page,
  TransactionType,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function toQueryString(filters: Filters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  return params.toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError("Could not reach the server", 0);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg?: string }) => item.msg).join("; ")
          : `Server error (${response.status})`;
    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export function fetchListings(filters: Filters): Promise<Page<ListingSummary>> {
  return request<Page<ListingSummary>>(`/listings?${toQueryString(filters)}`);
}

export function fetchListing(id: number): Promise<ListingDetail> {
  return request<ListingDetail>(`/listings/${id}`);
}

export function searchByIntent(query: string): Promise<IntentResponse> {
  return request<IntentResponse>("/search/intent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export function fetchCities(transactionType: TransactionType): Promise<string[]> {
  return request<string[]>(`/listings/cities?transaction_type=${transactionType}`);
}