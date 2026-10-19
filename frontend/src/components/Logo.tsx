// Doubloon: a coin in the site's accent blue with a white D, next to the wordmark.
// Same geometry as public/brand/doubloon-mark.svg (high-resolution files in public/brand).
export function CoinMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="16" fill="var(--accent)" />
      <circle cx="16" cy="16" r="13.1" fill="none" stroke="#fff" strokeOpacity="0.28" strokeWidth="0.9" />
      <path d="M10.4 8.5H14.9A7.5 7.5 0 0 1 14.9 23.5H10.4ZM13.4 11.5H14.9A4.5 4.5 0 0 1 14.9 20.5H13.4Z" fill="#fff" fillRule="evenodd" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight">
      <CoinMark />
      <span>Doubloon</span>
    </span>
  );
}
