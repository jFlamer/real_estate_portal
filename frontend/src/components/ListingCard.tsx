import { Link } from "react-router-dom";

import {
  formatArea,
  formatLayout,
  formatLocation,
  formatMonthlyTotal,
  formatPrice,
  formatPricePerM2,
} from "../format";
import type { ListingSummary } from "../types";

interface Props {
  listing: ListingSummary;
}

export function ListingCard({ listing }: Props) {
  const pricePerM2 = formatPricePerM2(listing.price, listing.area);
  const monthlyTotal = formatMonthlyTotal(listing);
  const cover = listing.image_urls?.[0];

  return (
    <article className="card">
      <Link to={`/listing/${listing.id}`} className="card-link">
        {/* alt="" on purpose: the heading right below already names the listing,
            so describing the photo would only repeat it for screen readers */}
        {cover ? (
          <img className="card-photo" src={cover} alt="" loading="lazy" />
        ) : (
          <div className="card-photo card-photo-empty">No photo</div>
        )}
        <h2 className="card-title">{listing.title ?? "Untitled listing"}</h2>
      </Link>

      <p className="card-location">{formatLocation(listing)}</p>

      <p className="card-price">
        {formatPrice(listing)}
        {pricePerM2 && <span className="card-price-unit">{pricePerM2}</span>}
      </p>

      {monthlyTotal && <p className="card-total">{monthlyTotal} incl. fees</p>}

      <p className="card-layout">
        {formatArea(listing.area)} · {formatLayout(listing)}
      </p>

      <div className="badges">
        {listing.open_kitchen === true && <span className="badge">Open-plan kitchen</span>}
        {listing.open_kitchen === false && <span className="badge">Separate kitchen</span>}
        {listing.market === "primary" && <span className="badge">New development</span>}
        {listing.layout_confidence === "low" && (
          <span className="badge badge-warning" title="Layout estimated: the description does not spell it out directly">
            Layout estimated
          </span>
        )}
      </div>
    </article>
  );
}