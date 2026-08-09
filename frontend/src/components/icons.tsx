export function StatsIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M3 3v18h18M7 15l4-6 4 3 5-8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function RagIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path
        d="M12 3a5 5 0 00-3 9 3 3 0 00-1 2v1h8v-1a3 3 0 00-1-2 5 5 0 00-3-9zM9 20h6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Caret({ open }: { open: boolean }) {
  return <span className={`caret${open ? " open" : ""}`}>&#9656;</span>;
}
