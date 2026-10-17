"use client";

import { useEffect, useState } from "react";
import { AddressLink, Card, TxLink, atomicToUsdc, usdc } from "@/components/ui";
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

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-bad">{error}</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Revenue" value={stats ? usdc(stats.revenue_usdc) : "—"} highlight />
        <Stat label="Total requests" value={stats ? String(stats.requests) : "—"} />
        <Stat label="Paid requests" value={stats ? String(stats.paid_requests) : "—"} />
        <Stat label="Average transaction" value={stats ? usdc(stats.average_usdc) : "—"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Transactions" className="lg:col-span-3">
          {!txs.length ? (
            <p className="text-sm text-muted">No sale yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="pb-2 pr-4 font-normal">Time</th>
                    <th className="pb-2 pr-4 font-normal">Offer</th>
                    <th className="pb-2 pr-4 font-normal">Payer</th>
                    <th className="pb-2 pr-4 text-right font-normal">Amount</th>
                    <th className="pb-2 font-normal">Tx hash</th>
                  </tr>
                </thead>
                <tbody>
                  {txs.map((t) => (
                    <tr
                      key={t.tx_id}
                      onClick={() => openAudit(t.offer_id)}
                      className={`cursor-pointer border-t border-border hover:bg-surface-2 ${audit?.offer.offer_id === t.offer_id ? "bg-surface-2" : ""}`}
                    >
                      <td className="py-2.5 pr-4 font-mono text-xs text-muted">{new Date(t.ts).toLocaleTimeString()}</td>
                      <td className="pr-4 font-mono text-xs">{t.offer_id}</td>
                      <td className="pr-4" onClick={(e) => e.stopPropagation()}>
                        <AddressLink address={t.payer} />
                      </td>
                      <td className="pr-4 text-right font-mono">{atomicToUsdc(t.amount_atomic).toFixed(2)}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <TxLink hash={t.tx_hash} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-muted">Click a sale to see its audit trail.</p>
        </Card>

        <Card title="Audit" className="lg:col-span-2">
          {!audit ? <p className="text-sm text-muted">Select a transaction.</p> : <AuditView audit={audit} />}
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${highlight ? "text-ok" : ""}`}>{value}</div>
    </div>
  );
}

function AuditView({ audit }: { audit: Audit }) {
  const { offer, agent, messages, transaction } = audit;
  return (
    <div className="animate-fade-in space-y-4 text-sm">
      <Section title="Agent identity (KYA)">
        <Row k="Agent" v={<span className="font-mono">{agent.agent_id}</span>} />
        <Row k="Wallet" v={<AddressLink address={agent.wallet_address} />} />
        <Row k="Status" v={<span className="text-ok">{agent.status}</span>} />
      </Section>
      <Section title="Offer">
        <Row k="Offer" v={<span className="font-mono">{offer.offer_id}</span>} />
        <Row k="Scope" v={offer.scope} />
        <Row k="Tier" v={<span className="font-mono">{offer.tier}</span>} />
        <Row k="Price" v={usdc(offer.price_usdc)} />
        <Row k="Content" v={<span className="font-mono text-xs">{offer.content_ids.join(", ")}</span>} />
        <Row k="License" v={offer.license} />
      </Section>
      <Section title="Conversation">
        <div className="space-y-2">
          {messages.map((m, i) => (
            <div key={i} className={`rounded-lg p-2.5 ${m.role === "buyer" ? "bg-background" : "bg-accent/10"}`}>
              <div className="text-[11px] text-muted">{m.role === "buyer" ? "Buyer agent" : "Sales agent"}</div>
              {m.content}
            </div>
          ))}
        </div>
      </Section>
      {transaction && (
        <Section title="Payment">
          <Row k="Amount" v={usdc(atomicToUsdc(transaction.amount_atomic))} />
          <Row k="Pay to" v={<AddressLink address={transaction.pay_to} />} />
          <Row k="Status" v={<span className="text-ok">{transaction.status}</span>} />
          <Row k="Tx hash" v={<TxLink hash={transaction.tx_hash} />} />
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">{title}</div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="w-20 shrink-0 text-muted">{k}</span>
      <span className="min-w-0 break-words">{v}</span>
    </div>
  );
}
