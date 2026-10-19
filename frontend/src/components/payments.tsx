"use client";

// Payments on the chain: animated counters (live view) and the public payment history (dashboard).
import { useEffect, useRef, useState } from "react";
import { TxLink, atomicToUsdc, toDate } from "@/components/ui";
import type { AppEvent, Transaction } from "@/lib/types";

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

export type Payment = {
  key: string;
  ts: string;
  amount: number;
  hash: string | null;
  state: "settling" | "confirmed" | "refused";
  count?: number;
};

// Confirmed payments come from the recorded sales (GET /transactions), so the history survives reloads.
// Events add what the table cannot show: a payment being settled, and a replay that was refused.
export function paymentsOf(txs: Transaction[], events: AppEvent[], now: number): Payment[] {
  const out: Payment[] = txs
    .filter((x) => x.status === "settled")
    .map((x) => ({ key: x.tx_id, ts: toDate(x.ts).toISOString(), amount: atomicToUsdc(x.amount_atomic), hash: x.tx_hash, state: "confirmed" as const }));
  const lastSettled = out.reduce((m, p) => (p.ts > m ? p.ts : m), "");
  for (const e of events) {
    if (e.type === "payment_verified" && e.ts > lastSettled && now - Date.parse(e.ts) < 120_000) {
      const settled = events.some((x) => x.type === "payment_settled" && x.session_id === e.session_id && x.ts >= e.ts);
      if (!settled) out.push({ key: `v${e.event_id ?? e.ts}`, ts: e.ts, amount: usdcIn(e.summary), hash: null, state: "settling" });
    }
    if (e.type === "replay_rejected") out.push({ key: `r${e.event_id ?? e.ts}`, ts: e.ts, amount: 0, hash: null, state: "refused" });
  }
  // Several replays in a row are one story: keep a single card with a count.
  const merged: Payment[] = [];
  for (const p of out.sort((a, b) => (a.ts < b.ts ? 1 : -1))) {
    const prev = merged.at(-1);
    if (p.state === "refused" && prev?.state === "refused") prev.count = (prev.count ?? 1) + 1;
    else merged.push({ ...p });
  }
  return merged;
}

export function PaymentCard({ payment: p, fresh }: { payment: Payment; fresh: boolean }) {
  if (p.state === "refused")
    return (
      <div className="animate-fade-in flex items-center gap-3 rounded-xl border border-dashed border-bad/40 px-3.5 py-2.5 text-sm">
        <span className="grid size-6 place-items-center rounded-full bg-bad/10 text-xs text-bad">✕</span>
        <div className="min-w-0 flex-1">
          <div className="font-medium text-bad">
            Replayed payment refused{p.count && p.count > 1 ? <span className="ml-1.5 text-xs font-normal">×{p.count}</span> : null}
          </div>
          <div className="text-xs text-muted">Nothing moved on-chain · {clock(p.ts)}</div>
        </div>
      </div>
    );
  const settling = p.state === "settling";
  return (
    <div className={`rounded-xl border px-3.5 py-3 transition-colors duration-1000 ${fresh ? "animate-fade-in border-ok/40 bg-ok/5" : "border-border bg-background"}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-lg font-semibold tabular-nums">
          {p.amount.toFixed(2)} <span className="text-xs font-normal text-muted">USDC</span>
        </span>
        {settling ? (
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <span className="size-1.5 animate-pulse rounded-full bg-accent" /> Settling
          </span>
        ) : (
          <span className={`flex items-center gap-1 text-xs font-medium text-ok ${fresh ? "animate-pop" : ""}`}>✓ Confirmed</span>
        )}
      </div>
      <div className="my-2.5 flex items-center gap-2 text-[10px] text-muted">
        <span>Agent</span>
        <div className="relative h-2.5 flex-1">
          <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
          <span
            className={`absolute inset-x-0 top-1/2 h-px origin-left -translate-y-1/2 bg-ok/60 transition-transform duration-700 ${settling ? "scale-x-0" : "scale-x-100"}`}
          />
          {settling || fresh ? (
            <span className={`absolute top-0 size-2.5 rounded-full bg-ok shadow-[0_0_0_3px_rgba(5,150,105,0.15)] ${settling ? "animate-travel-loop" : "animate-travel"}`} />
          ) : (
            <span className="absolute right-0 top-0.5 size-1.5 rounded-full bg-ok/70" />
          )}
        </div>
        <span>You</span>
      </div>
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{when(new Date(p.ts))}</span>
        {p.hash ? <TxLink hash={p.hash} /> : <span>waiting for the block…</span>}
      </div>
    </div>
  );
}
