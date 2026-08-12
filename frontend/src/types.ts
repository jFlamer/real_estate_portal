export type PriceStatus = "fixed" | "negotiable" | "unknown";
export type Market = "primary" | "secondary" | "unknown";
export type LayoutConfidence = "high" | "low";
export type LayoutSource = "llm" | "heuristic";
export type TransactionType = "sale" | "rent";

export type SortOption =
  | "newest"
  | "price_asc"
  | "price_desc"
  | "area_asc"
  | "area_desc";

export interface ListingSummary {
  id: number;
  transaction_type: TransactionType;
  title: string | null;
  price: number | null;
  price_status: PriceStatus;
  /** Building/admin fee as stated in the listing; null means it is not stated. */
  monthly_fee: number | null;
  area: number | null;
  rooms: number | null;
  floor: number | null;

  bedrooms: number | null;
  open_kitchen: boolean | null;
  layout_confidence: LayoutConfidence;
  layout_source: LayoutSource;

  city: string | null;
  district: string | null;
  market: Market;
  /** URLs on the portal's CDN — photos are linked, never rehosted. */
  image_urls: string[];
  source_url: string;
}


export interface ListingDetail extends ListingSummary {
  description: string;
  source: string;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Filters {
  transaction_type?: TransactionType;
  q?: string;
  city?: string;
  district?: string;
  price_min?: number;
  price_max?: number;
  /** Rent only: compare the budget against rent + building fee. */
  include_fees?: boolean;
  area_min?: number;
  area_max?: number;
  rooms_min?: number;
  bedrooms_min?: number;
  open_kitchen?: boolean;
  market?: Market;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}