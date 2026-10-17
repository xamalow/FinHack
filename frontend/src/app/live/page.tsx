"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Card, TxLink, AddressLink, shortHex } from "@/components/ui";
import * as api from "@/lib/api";
import { BUYER_WALLET } from "@/lib/config";
import type { Actor, AppEvent } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";

const COLUMNS: { title: string; actors: Actor[] }[] = [
  { title: "Buyer agent", actors: ["buyer"] },
  { title: "Gateway & Sales agent", actors: ["gateway", "sales_agent", "facilitator"] },
  { title: "Blockchain", actors: ["chain"] },
];

const PRESETS = [
  { label: "Sale 0.10", mission: "Find the 2025 European market share of the leading battery manufacturer." },
  { label: "Sale 2.00", mission: "Get the full 2025 battery manufacturer ranking with methodology." },
  { label: "Security", mission: "Security sequence: prompt injection, replayed payment, offer above budget." },
];

const BAD = /rejected|refused|injection_ignored|no_match/;
const GOOD = /verified|confirmed|settled|delivered|data_received|mission_done|validated|granted/;
const WARN = /approval_requested|payment_required/;

function tone(type: string) {
  if (BAD.test(type)) return "border-l-bad text-bad";
  if (WARN.test(type)) return "border-l-warn text-warn";
  if (GOOD.test(type)) return "border-l-ok text-ok";
  return "border-l-border text-muted";
}

function findHash(p: Record<string, unknown>): string | null {
  const h = p.tx_hash ?? p.transaction;
  return typeof h === "string" && /^0x[0-9a-fA-F]{64}$/.test(h) ? h : null;
}

export default function LiveView() {
  const [mission, setMission] = useState(PRESETS[0].mission);
  const [budget, setBudget] = useState(5);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AppEvent | null>(null);
  const [since, setSince] = useState(0);
  const [publisherWallet, setPublisherWallet] = useState<string | null>(null);
  const [balances, setBalances] = useState<{ buyer: number | null; publisher: number | null }>({ buyer: null, publisher: null });
  const [flash, setFlash] = useState(false);

  const lastBuyer = useRef<number | null>(null);
  const refreshBalances = useCallback(async () => {
    try {
      const [buyer, publisher] = await Promise.all([
        api.getBalance(BUYER_WALLET),
        publisherWallet ? api.getBalance(publisherWallet) : Promise.resolve(null),
      ]);
      if (lastBuyer.current !== null && lastBuyer.current !== buyer) {
        setFlash(true);
        setTimeout(() => setFlash(false), 1200);
      }
      lastBuyer.current = buyer;
      setBalances({ buyer, publisher });
    } catch {
      // gateway not reachable yet, keep last values
    }
  }, [publisherWallet]);
  const refreshRef = useRef(refreshBalances);
  useEffect(() => {
    refreshRef.current = refreshBalances;
  }, [refreshBalances]);

  const { events } = useEventStream((e) => {
    if (e.type === "balance_changed") void refreshRef.current();
    if (e.type === "mission_done" || e.type === "offer_refused_budget") setRunning(false);
  });

  useEffect(() => {
    api.getManifest().then((m) => setPublisherWallet(m.payment.pay_to), () => {});
  }, []);

  // agent.md asks for a 2 second balance poll during an active session.
  useEffect(() => {
    void refreshBalances();
    const t = setInterval(refreshBalances, 2000);
    return () => clearInterval(t);
  }, [refreshBalances]);

  const visible = useMemo(() => events.slice(since).filter((e) => e.session_id), [events, since]);

  const pendingApproval = useMemo(() => {
    const granted = new Set(visible.filter((e) => e.type === "approval_granted").map((e) => e.payload.offer_id));
    return visible.findLast((e) => e.type === "approval_requested" && !granted.has(e.payload.offer_id)) ?? null;
  }, [visible]);

  const run = async () => {
    setError(null);
    setRunning(true);
    try {
      await api.runBuyer(mission, budget);
    } catch (e) {
      setError(String(e));
      setRunning(false);
    }
  };

  const approve = async () => {
    if (!pendingApproval) return;
    try {
      await api.approve(String(pendingApproval.payload.offer_id), pendingApproval.session_id);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <label className="flex-1 text-xs text-muted">
            Mission
            <input
              value={mission}
              onChange={(e) => setMission(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
            />
          </label>
          <label className="text-xs text-muted">
            Budget (USDC)
            <input
              type="number"
              step="0.1"
              min="0"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="mt-1 block w-28 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
            />
          </label>
          <Button onClick={run} disabled={running || !mission.trim()}>
            {running ? "Running…" : "Run agent"}
          </Button>
          <Button variant="ghost" onClick={() => setSince(events.length)}>
            Clear
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button key={p.label} onClick={() => setMission(p.mission)} className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:text-foreground">
              {p.label}
            </button>
          ))}
        </div>
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      </Card>

      {pendingApproval && (
        <div className="animate-fade-in flex flex-wrap items-center gap-4 rounded-xl border border-warn/50 bg-warn/10 p-4">
          <div className="flex-1">
            <div className="font-medium text-warn">Human approval required</div>
            <div className="text-sm">{pendingApproval.summary}</div>
          </div>
          <Button variant="warn" onClick={approve}>
            Approve {Number(pendingApproval.payload.price_usdc).toFixed(2)} USDC
          </Button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {COLUMNS.map((col) => (
          <Card key={col.title} title={col.title} className="flex min-h-[60vh] flex-col">
            {col.actors.includes("chain") && (
              <div className="mb-4 grid grid-cols-2 gap-3">
                <Balance label="Buyer" address={BUYER_WALLET} value={balances.buyer} flash={flash} />
                <Balance label="Publisher" address={publisherWallet} value={balances.publisher} flash={flash} />
              </div>
            )}
            <EventList events={visible.filter((e) => col.actors.includes(e.actor))} onSelect={setSelected} />
          </Card>
        ))}
      </div>

      {selected && <PayloadDrawer event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Balance({ label, address, value, flash }: { label: string; address: string | null; value: number | null; flash: boolean }) {
  return (
    <div className={`rounded-lg border bg-background p-3 transition-colors ${flash ? "border-ok" : "border-border"}`}>
      <div className="flex items-center justify-between text-xs text-muted">
        {label}
        {address && <AddressLink address={address} />}
      </div>
      <div className="mt-1 font-mono text-xl">{value === null ? "—" : value.toFixed(2)}</div>
      <div className="text-xs text-muted">USDC on-chain</div>
    </div>
  );
}

function EventList({ events, onSelect }: { events: AppEvent[]; onSelect: (e: AppEvent) => void }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), [events.length]);

  if (!events.length) return <p className="text-sm text-muted">Waiting for events…</p>;
  return (
    <div className="max-h-[60vh] space-y-1.5 overflow-y-auto pr-1">
      {events.map((e, i) => {
        const hash = findHash(e.payload);
        return (
          <button
            key={e.event_id ?? `${e.ts}${i}`}
            onClick={() => onSelect(e)}
            className={`animate-fade-in block w-full rounded-md border-l-2 bg-background px-3 py-2 text-left hover:bg-surface-2 ${tone(e.type)}`}
          >
            <div className="flex items-center gap-2 text-[11px]">
              <span className="font-mono">{e.type}</span>
              <span className="ml-auto font-mono text-muted">{new Date(e.ts).toLocaleTimeString()}</span>
            </div>
            <div className="mt-0.5 text-sm text-foreground">{e.summary}</div>
            {hash && (
              <div className="mt-1 text-xs" onClick={(ev) => ev.stopPropagation()}>
                <TxLink hash={hash} />
              </div>
            )}
          </button>
        );
      })}
      <div ref={end} />
    </div>
  );
}

function PayloadDrawer({ event, onClose }: { event: AppEvent; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-surface p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-sm text-accent">{event.type}</div>
            <div className="mt-1">{event.summary}</div>
            <div className="mt-1 text-xs text-muted">
              {event.actor} · {event.session_id && shortHex(event.session_id, 12, 0)} · {event.ts}
            </div>
          </div>
          <button onClick={onClose} className="text-muted hover:text-foreground">
            ✕
          </button>
        </div>
        <pre className="mt-4 overflow-x-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed">{JSON.stringify(event.payload, null, 2)}</pre>
      </div>
    </div>
  );
}
