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

export function CounterTile({ label, value, unit, right, accent }: { label: string; value: number | null; unit: string; right?: React.ReactNode; accent?: boolean }) {
  const shown = useTween(value);
  const [delta, setDelta] = useState<{ amount: number; at: number } | null>(null);
  const prev = useRef(value);
  useEffect(() => {
    const before = prev.current;
    prev.current = value;
    if (value === null || before === null || Math.abs(value - before) < 1e-9) return;
    const t0 = setTimeout(() => setDelta({ amount: value - before, at: Date.now() }), 0);
    const t1 = setTimeout(() => setDelta(null), 2600);
    return () => {
      clearTimeout(t0);
      clearTimeout(t1);
    };
  }, [value]);
  const up = delta && delta.amount > 0;
  return (
    <div
      className={`relative rounded-xl border px-3.5 py-2.5 transition-colors duration-500 ${
        up ? "border-ok/50 bg-ok/5" : accent ? "border-ok/20 bg-ok/[0.03]" : "border-border bg-surface"
      }`}
    >
      <div className="text-[11px] text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-xl font-semibold tabular-nums ${accent ? "text-ok" : ""}`}>
        {shown === null ? "—" : shown.toFixed(2)}
        <span className="ml-1 text-xs font-normal text-muted">{unit}</span>
      </div>
      {right && <div className="mt-0.5 truncate text-[11px] text-muted">{right}</div>}
      {delta && (
        <span key={delta.at} className={`animate-pop absolute right-3 top-7 text-xs font-semibold ${up ? "text-ok" : "text-muted"}`}>
          {up ? "+" : "−"}
          {Math.abs(delta.amount).toFixed(2)}
        </span>
      )}
    </div>
  );
}
