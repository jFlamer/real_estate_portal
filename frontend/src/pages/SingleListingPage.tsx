import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, fetchListing } from "../api/client";
import {
  MARKET_LABELS,
  formatArea,
  formatFee,
  formatLayout,
  formatLocation,
  formatMonthlyTotal,
  formatPrice,
  formatPricePerM2,
} from "../format";
import type { ListingDetail } from "../types";

export function SingleListingPage() {
  const { id } = useParams<{ id: string }>();
  const [listing, setListing] = useState<ListingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    fetchListing(Number(id))
      .then((detail) => {
        if (active) setListing(detail);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(cause instanceof ApiError ? cause.message : "Something went wrong");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [id]);

  if (loading) return <p className="state">Loading…</p>;

  if (error || !listing) {
    return (
      <div className="state state-error" role="alert">
        <p>{error ?? "Listing not found"}</p>
        <Link to="/">← Back to results</Link>
      </div>
    );
  }

  const pricePerM2 = formatPricePerM2(listing.price, listing.area);
  const monthlyTotal = formatMonthlyTotal(listing);

  return (
    <article className="detail">
      <button type="button" className="link-button" onClick={() => history.back()}>
        ← Back to results
      </button>

      {listing.image_urls?.length > 0 && (
        <div className="gallery">
          {listing.image_urls.map((url, index) => (
            <img key={url} src={url} alt="" loading={index === 0 ? "eager" : "lazy"} />
          ))}
        </div>
      )}

      <h1>{listing.title ?? "Untitled listing"}</h1>
      <p className="detail-location">{formatLocation(listing)}</p>

      <p className="detail-price">
        {formatPrice(listing)}
        {pricePerM2 && <span className="card-price-unit">{pricePerM2}</span>}
      </p>

      {monthlyTotal && <p className="detail-total">{monthlyTotal} including building fees</p>}

      <dl className="detail-specs">
        <div>
          <dt>Area</dt>
          <dd>{formatArea(listing.area)}</dd>
        </div>
        <div>
          <dt>Layout</dt>
          <dd>{formatLayout(listing)}</dd>
        </div>
        <div>
          <dt>Kitchen</dt>
          <dd>
            {listing.open_kitchen === null
              ? "No information"
              : listing.open_kitchen
                ? "Open to living room"
                : "Separate room"}
          </dd>
        </div>
        <div>
          <dt>Floor</dt>
          <dd>{listing.floor === null ? "-" : listing.floor === 0 ? "Ground floor" : listing.floor}</dd>
        </div>
        <div>
          <dt>Market</dt>
          <dd>{MARKET_LABELS[listing.market]}</dd>
        </div>
        <div>
          <dt>Building fee</dt>
          <dd>{formatFee(listing.monthly_fee)}</dd>
        </div>
      </dl>

      {listing.latitude !== null && listing.longitude !== null && (
        <a
          className="source-link"
          href={`https://www.openstreetmap.org/?mlat=${listing.latitude}&mlon=${listing.longitude}#map=17/${listing.latitude}/${listing.longitude}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Show on map ↗
        </a>
      )}

      <p className="detail-provenance">
        Layout{" "}
        {listing.layout_source === "llm"
          ? "extracted from the description by a language model"
          : "estimated from the room count"}
        , confidence: {listing.layout_confidence}.
      </p>

      <section className="detail-description">
        <h2>Description</h2>
        {listing.description.split(/\n+/).map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </section>

      <a className="source-link" href={listing.source_url} target="_blank" rel="noopener noreferrer">
        View original listing on {listing.source} ↗
      </a>
    </article>
  );
}