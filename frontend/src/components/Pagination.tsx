interface Props {
  page: number;
  pages: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pages, onChange }: Props) {
  if (pages <= 1) return null;

  return (
    <nav className="pagination" aria-label="Result pages">
      <button type="button" onClick={() => onChange(page - 1)} disabled={page <= 1}>
        ← Previous
      </button>
      <span aria-current="page">
        Page {page} of {pages}
      </span>
      <button type="button" onClick={() => onChange(page + 1)} disabled={page >= pages}>
        Next →
      </button>
    </nav>

  );
}