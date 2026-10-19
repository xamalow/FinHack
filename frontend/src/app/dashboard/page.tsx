"use client";

import { useEffect, useState } from "react";
import { useTween, when } from "@/components/payments";
import { AddressLink, Card, TxLink, atomicToUsdc, toDate, usdc } from "@/components/ui";
import * as api from "@/lib/api";
import type { Audit, PublisherStats, Transaction } from "@/lib/types";

export default function Dashboard() {
  const [stats, setStats] = useState<PublisherStats | null>(null);
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      Promise.all([api.getStats(), api.getTransactions()]).then(
        ([s, t]) => {
          setStats(s);
          setTxs(t);
          setError(null);
        },
        (e) => setError(String(e)),
      );
    void load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const openAudit = async (offerId: string) => {
    try {
      setAudit(await api.getAudit(offerId));
    } catch (e) {
      setError(String(e));
    }
  };

  const sales = [...txs].sort((a, b) => Number(b.ts) - Number(a.ts));
  const conversion = stats && stats.requests ? Math.round((100 * stats.paid_requests) / stats.requests) : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted">Every sale your sales agent made, with its full audit trail.</p>
        </div>
        <span className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
          <span className={`size-1.5 rounded-full ${error ? "bg-bad" : "animate-pulse bg-ok"}`} />
          {error ? "Gateway not reachable" : "Live · refreshed every 5 s"}
        </span>
      </div>
      {error && <p className="rounded-lg bg-bad/10 px-3 py-2 text-sm text-bad">{error}</p>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icon="💰" label="Revenue" value={stats?.revenue_usdc ?? null} unit="USDC" hint="Paid to your wallet, on-chain" accent />
        <Kpi icon="🧾" label="Sales" value={stats?.paid_requests ?? null} digits={0} hint={stats ? `out of ${stats.requests} requests${conversion !== null ? ` · ${conversion}% paid` : ""}` : ""} />
        <Kpi icon="⚖️" label="Average sale" value={stats?.average_usdc ?? null} unit="USDC" hint="Price set by what the agent asks for" />
        <Kpi icon="🤖" label="Agent requests" value={stats?.requests ?? null} digits={0} hint="Every call an agent made to a paid route" />
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[3fr_2fr]">
        <Card title="Sales" subtitle="Newest first. Click a sale to see its audit trail." right={<span className="text-xs tabular-nums text-muted">{sales.length} sales</span>}>
          {!sales.length ? (
            <p className="py-6 text-center text-sm text-muted">No sale yet.</p>
          ) : (
            <div className="-mx-4 -my-4 max-h-[62vh] overflow-auto">
              <table className="w-full whitespace-nowrap text-sm">
                <thead className="sticky top-0 z-10 bg-surface/95 text-left text-[11px] uppercase tracking-wide text-muted backdrop-blur">
                  <tr className="border-b border-border">
                    <th className="px-4 py-2.5 font-medium">When</th>
                    <th className="px-2 py-2.5 font-medium">Buyer</th>
                    <th className="px-2 py-2.5 text-right font-medium">Amount</th>
                    <th className="px-4 py-2.5 font-medium">Proof on-chain</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((t, i) => {
                    const active = audit?.offer.offer_id === t.offer_id;
                    return (
                      <tr
                        key={t.tx_id}
                        onClick={() => openAudit(t.offer_id)}
                        style={{ animationDelay: `${Math.min(i * 25, 400)}ms`, animationFillMode: "both" }}
                        className={`animate-fade-in cursor-pointer border-b border-border/70 transition-colors last:border-0 ${
                          active ? "bg-accent/[0.06] shadow-[inset_3px_0_0_var(--accent)]" : "hover:bg-surface-2/70"
                        }`}
                      >
                        <td className="px-4 py-2.5">
                          <div className="font-medium">{when(toDate(t.ts))}</div>
                          <div className="font-mono text-[11px] text-muted">{t.offer_id}</div>
                        </td>
                        <td className="px-2" onClick={(e) => e.stopPropagation()}>
                          <AddressLink address={t.payer} />
                        </td>
                        <td className="px-2 text-right">
                          <span className="inline-block rounded-full bg-ok/10 px-2.5 py-0.5 font-mono text-[13px] font-semibold tabular-nums text-ok">
                            +{atomicToUsdc(t.amount_atomic).toFixed(2)}
                          </span>
                        </td>
                        <td className="px-4 text-xs" onClick={(e) => e.stopPropagation()}>
                          {t.tx_hash ? <TxLink hash={t.tx_hash} /> : <span className="text-muted">{t.status}</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Audit" subtitle={audit ? `Sale ${audit.offer.offer_id}` : "Who bought what, the conversation and the payment"} className="lg:sticky lg:top-4">
          {!audit ? (
            <div className="py-10 text-center text-sm text-muted">
              <div className="mb-2 text-2xl">🔎</div>
              Select a sale on the left.
            </div>
          ) : (
            <AuditView key={audit.offer.offer_id} audit={audit} />
          )}
        </Card>
      </div>
    </div>
  );
}

function Kpi({ icon, label, value, unit, hint, digits = 2, accent }: { icon: string; label: string; value: number | null; unit?: string; hint?: string; digits?: number; accent?: boolean }) {
  const shown = useTween(value);
  return (
    <div
      className={`animate-fade-in rounded-2xl border p-4 shadow-sm transition-colors ${
        accent ? "border-ok/25 bg-gradient-to-br from-ok/[0.07] to-surface" : "border-border bg-surface"
      }`}
    >
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className={`grid size-7 place-items-center rounded-lg text-sm ${accent ? "bg-ok/15" : "bg-surface-2"}`}>{icon}</span>
        {label}
      </div>
      <div className={`mt-3 font-mono text-[26px] font-semibold leading-none tabular-nums ${accent ? "text-ok" : ""}`}>
        {shown === null ? "—" : shown.toFixed(digits)}
        {unit && <span className="ml-1.5 font-sans text-xs font-normal text-muted">{unit}</span>}
      </div>
      {hint && <div className="mt-2 truncate text-[11px] text-muted">{hint}</div>}
    </div>
  );
}

function AuditView({ audit }: { audit: Audit }) {
  const { offer, agent, messages, transaction } = audit;
  return (
    <div className="animate-fade-in space-y-5 text-sm">
      {agent && (
        <Section icon="🪪" title="Buyer identity (KYA)">
          <Row k="Agent" v={<span className="font-mono text-xs">{agent.agent_id}</span>} />
          <Row k="Wallet" v={<AddressLink address={agent.wallet_address} />} />
          <Row k="Status" v={<Pill ok>{agent.status}</Pill>} />
        </Section>
      )}
      <Section icon="🤝" title="What was sold">
        <Row k="Scope" v={offer.scope} />
        <Row k="Tier" v={<span className="font-mono text-xs">{offer.tier}</span>} />
        <Row k="Price" v={<span className="font-semibold">{usdc(offer.price_usdc)}</span>} />
        <Row k="Content" v={<span className="font-mono text-xs">{offer.content_ids.join(", ")}</span>} />
        <Row k="License" v={offer.license} />
      </Section>
      <Section icon="💬" title="Conversation">
        <div className="space-y-2">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "buyer" ? "justify-start" : "justify-end"}`}>
              <div
                className={`max-w-[88%] px-3 py-2 text-[13px] leading-snug ${
                  m.role === "buyer" ? "rounded-2xl rounded-bl-md bg-surface-2" : "rounded-2xl rounded-br-md bg-accent text-white"
                }`}
              >
                <div className={`mb-0.5 text-[10px] font-medium uppercase tracking-wide ${m.role === "buyer" ? "text-muted" : "text-white/70"}`}>
                  {m.role === "buyer" ? "Buyer's agent" : "Your sales agent"}
                </div>
                {m.content}
              </div>
            </div>
          ))}
          {!messages.length && <p className="text-xs text-muted">Conversation erased after the retention period. The sale record is kept.</p>}
        </div>
      </Section>
      {transaction && (
        <Section icon="⛓️" title="Payment">
          <Row k="Amount" v={<span className="font-semibold text-ok">{usdc(atomicToUsdc(transaction.amount_atomic))}</span>} />
          <Row k="Pay to" v={<AddressLink address={transaction.pay_to} />} />
          <Row k="Status" v={<Pill ok={transaction.status === "settled"}>{transaction.status}</Pill>} />
          {transaction.tx_hash && <Row k="Tx hash" v={<TxLink hash={transaction.tx_hash} />} />}
        </Section>
      )}
    </div>
  );
}

function Pill({ ok, children }: { ok?: boolean; children: React.ReactNode }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ok ? "bg-ok/10 text-ok" : "bg-surface-2 text-muted"}`}>{children}</span>;
}

function Section({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
        <span>{icon}</span>
        {title}
      </div>
      <div className="space-y-1.5 rounded-xl border border-border bg-background/60 p-3">{children}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="w-16 shrink-0 text-muted">{k}</span>
      <span className="min-w-0 break-words">{v}</span>
    </div>
  );
}
