import type { Filters, ListingSummary } from "./types";

const PLN = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "PLN",
  maximumFractionDigits: 0,
});

export function formatPrice(
  listing: Pick<ListingSummary, "price" | "price_status" | "transaction_type">,
): string {
  if (listing.price === null) return "Price on request";
  const price = listing.transaction_type === "rent"
    ? `${PLN.format(listing.price)}/month`
    : PLN.format(listing.price);
  return listing.price_status === "negotiable" ? `${price} (negotiable)` : price;
}

export function formatMonthlyTotal(
  listing: Pick<ListingSummary, "price" | "monthly_fee" | "transaction_type">,
): string | null {
  if (listing.transaction_type !== "rent") return null;
  if (listing.price === null || listing.monthly_fee === null) return null;
  return `${PLN.format(listing.price + listing.monthly_fee)}/month total`;
}

export function formatFee(monthlyFee: number | null): string {
  return monthlyFee === null ? "Not stated in the listing" : `${PLN.format(monthlyFee)}/month`;
}

export function formatArea(area: number | null): string {
  return area === null ? "—" : `${area.toLocaleString("en-GB")} m2`;
}

export function formatPricePerM2(price: number | null, area: number | null): string | null {
  if (price === null || area === null || area === 0) return null;
  return `${PLN.format(Math.round(price / area))}/m2`;
}


export function formatLocation(listing: Pick<ListingSummary, "city" | "district">): string {
  return [listing.city, listing.district].filter(Boolean).join(", ") || "Location unknown";
}

export function formatLayout(listing: Pick<ListingSummary, "rooms" | "bedrooms">): string {
  const parts: string[] = [];
  if (listing.rooms !== null) parts.push(plural(listing.rooms, "room"));
  if (listing.bedrooms !== null) parts.push(plural(listing.bedrooms, "bedroom"));
  return parts.join(" · ") || "Layout unknown";
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function describeFilters(filters: Filters): string[] {
  const parts: string[] = [];
  const renting = filters.transaction_type === "rent";

  parts.push(renting ? "to rent" : "for sale");
  if (filters.city) parts.push(filters.city);
  if (filters.bedrooms_min) parts.push(`${filters.bedrooms_min}+ separate bedrooms`);
  if (filters.rooms_min) parts.push(`${filters.rooms_min}+ rooms`);
  if (filters.open_kitchen === true) parts.push("open-plan kitchen");
  if (filters.open_kitchen === false) parts.push("separate kitchen");

  if (filters.area_min && filters.area_max) parts.push(`${filters.area_min}–${filters.area_max} m²`);
  else if (filters.area_min) parts.push(`from ${filters.area_min} m²`);
  else if (filters.area_max) parts.push(`up to ${filters.area_max} m²`);

  const money = (value: number) => `PLN ${value.toLocaleString("en-GB")}`;
  if (filters.price_min && filters.price_max) {
    parts.push(`${money(filters.price_min)}–${money(filters.price_max)}`);
  } else if (filters.price_min) parts.push(`from ${money(filters.price_min)}`);
  else if (filters.price_max) parts.push(`up to ${money(filters.price_max)}`);

  if (filters.include_fees) parts.push("fees included");
  if (filters.q) parts.push(`mentioning "${filters.q}"`);
  if (filters.sort === "price_asc") parts.push("cheapest first");
  if (filters.sort === "price_desc") parts.push("most expensive first");

  return parts;
}

export const MARKET_LABELS: Record<string, string> = {
  primary: "New development",
  secondary: "Resale",
  unknown: "Market unknown",
};