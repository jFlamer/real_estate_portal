import { useState } from "react";

import { ApiError, searchByIntent } from "../api/client";
import { describeFilters } from "../format";
import type { Filters as FilterValues } from "../types";

interface Props {
  onFilters: (filters: FilterValues) => void;
}

const EXAMPLES = [
  "renting with a flatmate, we each need our own bedroom, up to 4000 including fees",
  "cheap two-bedroom flat in Kraków with an open-plan kitchen",
];

export function IntentSearch({ onFilters }: Props) {
  const [query, setQuery] = useState("");
  const [understood, setUnderstood] = useState<string[] | null>(null);
  const [source, setSource] = useState<"llm" | "keywords" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async (text: string) => {
    const trimmed = text.trim();
    if (trimmed.length < 2) return;

    setLoading(true);
    setError(null);
    try {
      const response = await searchByIntent(trimmed);
      setUnderstood(describeFilters(response.filters));
      setSource(response.source);
      onFilters(response.filters);
    } catch (cause: unknown) {
      setError(cause instanceof ApiError ? cause.message : "Something went wrong");
      setUnderstood(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="intent">
      <form
        className="intent-form"
        onSubmit={(event) => {
          event.preventDefault();
          void run(query);
        }}
      >
        <label className="intent-label" htmlFor="intent-input">
          Describe what you need
        </label>
        <div className="intent-row">
          <input
            id="intent-input"
            type="text"
            value={query}
            maxLength={400}
            placeholder="e.g. two of us renting, each needs their own room, max 4000 with fees"
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit" disabled={loading || query.trim().length < 2}>
            {loading ? "Reading…" : "Search"}
          </button>
        </div>
      </form>

      {!understood && !error && (
        <p className="intent-hint">
          Try:{" "}
          {EXAMPLES.map((example, index) => (
            <span key={example}>
              {index > 0 && " · "}
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  setQuery(example);
                  void run(example);
                }}
              >
                {example}
              </button>
            </span>
          ))}
        </p>
      )}

      {error && (
        <p className="intent-error" role="alert">
          {error}
        </p>
      )}

      {understood && (
        <p className="intent-understood">
          <strong>Understood:</strong> {understood.join(" · ")}
          {source === "keywords" && (
            <span className="intent-fallback">
              {" "}
              — matched by keywords, the language model was unavailable
            </span>
          )}
        </p>
      )}
    </section>
  );
}
