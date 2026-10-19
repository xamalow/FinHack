// Doubloon: a geometric D whose counter is a coin, in the accent blue gradient (blue-500 → #2563eb → blue-700).
// Same shape as public/brand/doubloon-mark.svg; high-resolution files and the app icon are in public/brand.
import { useId } from "react";

export function CoinMark({ size = 22 }: { size?: number }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3b82f6" />
          <stop offset="0.5" stopColor="var(--accent)" />
          <stop offset="1" stopColor="#1d4ed8" />
        </linearGradient>
      </defs>
      <path
        d="M1.4 0H7A7 7 0 0 1 7 14H1.4A1.4 1.4 0 0 1 0 12.6V1.4A1.4 1.4 0 0 1 1.4 0ZM10.4 7A3.4 3.4 0 1 0 3.6 7A3.4 3.4 0 1 0 10.4 7Z"
        fill={`url(#${id})`}
        fillRule="evenodd"
      />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2 text-[17px] font-semibold tracking-[-0.035em]">
      <CoinMark size={20} />
      <span>Doubloon</span>
    </span>
  );
}
