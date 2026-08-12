import type { Filters as FilterValues, Market, SortOption, TransactionType } from "../types";

interface Props {
  values: FilterValues;
  cities: string[];
  onChange: (patch: Partial<FilterValues>) => void;
  onReset: () => void;
}

const SORT_LABELS: Record<SortOption, string> = {
  newest: "Newest first",
  price_asc: "Cheapest first",
  price_desc: "Most expensive first",
  area_asc: "Smallest first",
  area_desc: "Largest first",
};

export function Filters({ values, cities, onChange, onReset }: Props) {
    const transaction: TransactionType = values.transaction_type ?? "sale";
    const renting = transaction === "rent";
    const withFees = values.include_fees === true;
    const activeCount = Object.entries(values).filter(
    ([key, value]) => value !== undefined && key !== "transaction_type" && key !== "sort" && key !== "page",
  ).length;

    const numeric = (key: keyof FilterValues) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const raw = event.target.value;
    onChange({ [key]: raw === "" ? undefined : Number(raw) } as Partial<FilterValues>);
  };
  const switchTo = (next: TransactionType) => {
    if (next === transaction) return;
    // widełki cenowe i doliczanie opłat są związane z rynkiem, więc znikają
    // razem z nim — 800 000 i 2 600 to nieporównywalne liczby
    onChange({
      transaction_type: next,
      price_min: undefined,
      price_max: undefined,
      include_fees: undefined,
    });
  };


  return (
      <aside className="filters">
          <div className="segmented" role="group" aria-label="Transaction type">
              <button
                  type="button"
                  className={transaction === "sale" ? "segment segment-active" : "segment"}
                  aria-pressed={transaction === "sale"}
                  onClick={() => switchTo("sale")}
              >
                  Buy
              </button>
              <button
                  type="button"
                  className={renting ? "segment segment-active" : "segment"}
                  aria-pressed={renting}
                  onClick={() => switchTo("rent")}
              >
                  Rent
              </button>
          </div>

          <div className="filters-header">
              <h2>Filters{activeCount > 0 && ` (${activeCount})`}</h2>
              <button
                  type="button"
                  className="link-button"
                  onClick={onReset}
                  disabled={activeCount === 0}
              >
                  Clear all
              </button>
          </div>

          <label className="field">
              <span>Search in text</span>
              <input
                  type="search"
                  value={values.q ?? ""}
                  placeholder="e.g. terrace, lift, garage"
                  onChange={(event) => onChange({q: event.target.value || undefined})}
              />
          </label>

          <label className="field">
              <span>City</span>
              <select
                  value={values.city ?? ""}
                  onChange={(event) => onChange({city: event.target.value || undefined})}
              >
                  <option value="">All</option>
                  {cities.map((city) => (
                      <option key={city} value={city}>
                          {city}
                      </option>
                  ))}
              </select>
          </label>

          <fieldset className="field-group">
              <legend>
                  {renting
                      ? withFees
                          ? "Total monthly cost (PLN)"
                          : "Monthly rent (PLN)"
                      : "Price (PLN)"}
              </legend>
              <input
                  type="number"
                  min={0}
                  step={renting ? 250 : 10000}
                  placeholder="from"
                  value={values.price_min ?? ""}
                  onChange={numeric("price_min")}
              />
              <input
                  type="number"
                  min={0}
                  step={renting ? 250 : 10000}
                  placeholder="to"
                  value={values.price_max ?? ""}
                  onChange={numeric("price_max")}
              />
          </fieldset>

          {renting && (
              <label className="field-check">
                  <input
                      type="checkbox"
                      checked={withFees}
                      onChange={(event) => onChange({include_fees: event.target.checked || undefined})}
                  />
                  <span>
                      Count building fees towards my budget
                      <small>
                          Fees are stated in 4 of 5 listings; where they are missing the rent is
                          compared on its own.
                      </small>
                  </span>
              </label>
          )}

          <fieldset className="field-group">
              <legend>Area (m²)</legend>
              <input type="number" min={0} step={5} placeholder="from" value={values.area_min ?? ""}
                     onChange={numeric("area_min")}/>
              <input type="number" min={0} step={5} placeholder="to" value={values.area_max ?? ""}
                     onChange={numeric("area_max")}/>
          </fieldset>

          <label className="field field-highlight">
              <span>Separate bedrooms</span>
              <select
                  value={values.bedrooms_min ?? ""}
                  onChange={(event) =>
                      onChange({bedrooms_min: event.target.value === "" ? undefined : Number(event.target.value)})
                  }
              >
                  <option value="">Any</option>
                  <option value="1">1+</option>
                  <option value="2">2+</option>
                  <option value="3">3+</option>
                  <option value="4">4+</option>
              </select>
              <small>
                  Closable rooms you can sleep in, excluding the living room and walk-through rooms.
                  {renting && " One per flatmate."}
              </small>
          </label>

          <label className="field">
              <span>Kitchen</span>
              <select
                  value={values.open_kitchen === undefined ? "" : String(values.open_kitchen)}
                  onChange={(event) =>
                      onChange({open_kitchen: event.target.value === "" ? undefined : event.target.value === "true"})
                  }
              >
                  <option value="">Doesn't matter</option>
                  <option value="true">Open to living room</option>
                  <option value="false">Separate room</option>
              </select>
          </label>

          <label className="field">
              <span>Market</span>
              <select
                  value={values.market ?? ""}
                  onChange={(event) => onChange({market: (event.target.value || undefined) as Market | undefined})}
              >
                  <option value="">Any</option>
                  <option value="primary">New development</option>
                  <option value="secondary">Resale</option>
              </select>
          </label>

          <label className="field">
              <span>Sort by</span>
              <select
                  value={values.sort ?? "newest"}
                  onChange={(event) => onChange({sort: event.target.value as SortOption})}
              >
                  {Object.entries(SORT_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                          {label}
                      </option>
                  ))}
              </select>
          </label>
      </aside>
  );
}