"use client";

// Animated counters and time helpers shared by the live view and the dashboard.
import { useEffect, useRef, useState } from "react";

export const usdcIn = (s: string) => Number(/([\d.]+)\s*USDC/.exec(s)?.[1] ?? 0);
export const clock = (ts: string) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
export const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();
export const when = (d: Date) =>
  sameDay(d, new Date())
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], { day: "numeric", month: "short" }) + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export function useTween(value: number | null, ms = 800): number | null {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (value === null) return;
    const start = from.current ?? value;
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setShown(start + (value - start) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return shown;
}

// One digit of a rolling counter: a 0-9 strip that slides to the current digit, like a flight board.
function Digit({ d }: { d: number }) {
  return (
    <span className="relative inline-block h-[1em] w-[0.62em] overflow-hidden align-top">
      <span className="absolute inset-x-0 top-0 flex flex-col transition-transform duration-[1100ms] ease-[cubic-bezier(0.16,1,0.3,1)]" style={{ transform: `translateY(-${d}em)` }}>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className="block h-[1em] text-center leading-none">
            {i}
          </span>
        ))}
      </span>
    </span>
  );
}

// A number whose digits roll to their new value. Digits are keyed from the right, so units stay units.
export function RollingNumber({ value, digits = 2 }: { value: number; digits?: number }) {
  const text = value.toFixed(digits);
  return (
    <span className="inline-flex leading-none" aria-label={text}>
      {text.split("").map((ch, i) => {
        const key = text.length - i;
        return /\d/.test(ch) ? <Digit key={key} d={Number(ch)} /> : <span key={`s${key}`} className="inline-block h-[1em] leading-none">{ch}</span>;
      })}
    </span>
  );
}

export function CounterTile({ label, value, unit, right, accent }: { label: string; value: number | null; unit: string; right?: React.ReactNode; accent?: boolean }) {
  const [delta, setDelta] = useState<{ amount: number; at: number } | null>(null);
  const prev = useRef(value);
  useEffect(() => {
    const before = prev.current;
    prev.current = value;
    if (value === null || before === null || Math.abs(value - before) < 1e-9) return;
    const t0 = setTimeout(() => setDelta({ amount: value - before, at: Date.now() }), 0);
    const t1 = setTimeout(() => setDelta(null), 3200);
    return () => {
      clearTimeout(t0);
      clearTimeout(t1);
    };
  }, [value]);
  const up = !!delta && delta.amount > 0;
  return (
    <div
      className={`relative h-full overflow-hidden rounded-xl border px-3.5 py-2.5 transition-colors duration-700 ${
        up ? "animate-wallet-glow border-ok/60 bg-ok/[0.07]" : accent ? "border-ok/20 bg-ok/[0.03]" : "border-border bg-surface"
      }`}
    >
      {up && <span className="animate-wallet-sheen pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 bg-gradient-to-r from-transparent via-ok/15 to-transparent" />}
      <div className="flex items-center gap-1.5 text-[11px] text-muted">
        {label}
        {up && <span className="animate-pop rounded-full bg-ok px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide text-white">Paid</span>}
      </div>
      <div className={`mt-1 flex items-baseline font-mono text-xl font-semibold tabular-nums ${accent || up ? "text-ok" : ""}`}>
        {value === null ? "—" : <RollingNumber value={value} />}
        <span className="ml-1 font-sans text-xs font-normal text-muted">{unit}</span>
      </div>
      {right && <div className="mt-0.5 truncate text-[11px] text-muted">{right}</div>}
      {delta && (
        <span key={delta.at} className={`animate-float-up absolute right-3 top-2.5 rounded-full px-2 py-0.5 font-mono text-xs font-semibold ${up ? "bg-ok/15 text-ok" : "bg-surface-2 text-muted"}`}>
          {up ? "▲ +" : "−"}
          {Math.abs(delta.amount).toFixed(2)}
        </span>
      )}
    </div>
  );
}
