// Doubloon: a gold coin mark next to the wordmark.
export function CoinMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="doubloon-gold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F5D06F" />
          <stop offset="0.55" stopColor="#D4A72C" />
          <stop offset="1" stopColor="#A87C12" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="15" fill="url(#doubloon-gold)" />
      <circle cx="16" cy="16" r="11.5" fill="none" stroke="#FFF3C4" strokeOpacity="0.55" strokeWidth="1.2" />
      <path d="M12 9.5h4.3c4.1 0 6.7 2.6 6.7 6.5s-2.6 6.5-6.7 6.5H12z" fill="none" stroke="#7A5A0B" strokeWidth="2.2" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight">
      <CoinMark />
      <span>
        Doubloon<span className="font-normal text-muted">.ai</span>
      </span>
    </span>
  );
}
