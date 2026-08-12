import type { ListingSummary } from "./types";

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

/** Total monthly outlay for a rental: rent plus the stated building fee.
 *
 *  Returns null when the listing does not state a fee — we say so explicitly
 *  rather than presenting the bare rent as if it were the full cost. The fee
 *  is stated in 80 of 100 rentals and its median is 700 PLN, so ignoring it
 *  understates the real budget by roughly a quarter.
 */
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

export const MARKET_LABELS: Record<string, string> = {
  primary: "New development",
  secondary: "Resale",
  unknown: "Market unknown",
};