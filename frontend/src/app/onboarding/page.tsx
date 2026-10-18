"use client";

import { useEffect, useState } from "react";
import { useAccount, useConnect, useDisconnect, useSwitchChain } from "wagmi";
import { baseSepolia } from "wagmi/chains";
import { Button, Card, shortHex, usdc } from "@/components/ui";
import * as api from "@/lib/api";
import { DEMO_SITE_URL } from "@/lib/config";
import { mockRulesText } from "@/lib/mocks";
import type { CatalogItem, CatalogStatus, Manifest, Tier } from "@/lib/types";
import { labelFor } from "@/lib/eventLabels";
import { useEventStream } from "@/lib/useEventStream";

const STEPS = ["Website", "Catalog", "Pricing", "Wallet & activate"];
const SCAN_STAGES = ["scan_started", "scan_extracting", "scan_indexing", "scan_ready"];

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [tiers, setTiers] = useState<Tier[] | null>(null);

  return (
    <div className="mx-auto max-w-5xl">
      <ol className="mb-6 flex flex-wrap gap-2">
        {STEPS.map((s, i) => (
          <li key={s}>
            <button
              onClick={() => i < step && setStep(i)}
              className={`flex items-center gap-2 rounded-full border px-3 py-1 text-sm ${i === step ? "border-accent text-foreground" : i < step ? "border-ok/40 text-ok" : "border-border text-muted"}`}
            >
              <span className="font-mono text-xs">{i < step ? "✓" : i + 1}</span>
              {s}
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <ScanStep
          onDone={async () => {
            setCatalog(await api.getCatalog());
            setStep(1);
          }}
        />
      )}
      {step === 1 && <CatalogStep catalog={catalog} setCatalog={setCatalog} onNext={() => setStep(2)} />}
      {step === 2 && <RulesStep tiers={tiers} setTiers={setTiers} onNext={() => setStep(3)} />}
      {step === 3 && <ActivateStep />}
    </div>
  );
}

function ScanStep({ onDone }: { onDone: () => void }) {
  const [url, setUrl] = useState(DEMO_SITE_URL);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { events } = useEventStream();
  const [since, setSince] = useState(0);
  const scanEvents = events.slice(since).filter((e) => SCAN_STAGES.includes(e.type));
  const stage = Math.max(-1, ...scanEvents.map((e) => SCAN_STAGES.indexOf(e.type)));
  const ready = stage === SCAN_STAGES.length - 1;

  useEffect(() => {
    if (ready) {
      const t = setTimeout(onDone, 900);
      return () => clearTimeout(t);
    }
  }, [ready, onDone]);

  const start = async () => {
    setError(null);
    setSince(events.length);
    setScanning(true);
    try {
      await api.scan(url);
    } catch (e) {
      setError(String(e));
      setScanning(false);
    }
  };

  return (
    <Card title="Paste your website URL">
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:border-accent"
          placeholder="https://your-site.com"
        />
        <Button onClick={start} disabled={scanning || !url}>
          {scanning ? "Scanning…" : "Scan site"}
        </Button>
      </div>
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      {scanning && (
        <div className="mt-6">
          <div className="h-2 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full bg-accent transition-all duration-700" style={{ width: `${((stage + 1) / SCAN_STAGES.length) * 100}%` }} />
          </div>
          <ul className="mt-4 space-y-2 text-sm">
            {scanEvents.map((e) => {
              const l = labelFor(e.type);
              return (
                <li key={e.event_id ?? e.ts} className="animate-fade-in flex gap-3">
                  <span>{l.icon}</span>
                  <div>
                    <div className={`font-medium ${e.type === "scan_ready" ? "text-ok" : ""}`}>{l.title}</div>
                    <div className="text-muted">{e.summary}</div>
                  </div>
                </li>
              );
            })}
            {!ready && <li className="animate-pulse text-muted">…</li>}
          </ul>
        </div>
      )}
    </Card>
  );
}

const STATUS_OPTIONS: { key: CatalogStatus; icon: string; label: string; help: string; active: string }[] = [
  { key: "sellable", icon: "💰", label: "For sale", help: "Agents can buy it", active: "border-accent bg-accent text-white" },
  { key: "free", icon: "👀", label: "Free preview", help: "Agents read it for free", active: "border-ok bg-ok text-white" },
  { key: "excluded", icon: "🔒", label: "Keep private", help: "Never shown or sold", active: "border-bad bg-bad text-white" },
];

const TIER_LABEL: Record<CatalogItem["suggested_tier"], string> = {
  single_fact: "a single figure",
  small_table: "a small table",
  full_section: "the full section",
};

const humanize = (s: string) => s.replace(/_/g, " ");

function CatalogStep({ catalog, setCatalog, onNext }: { catalog: CatalogItem[]; setCatalog: (c: CatalogItem[]) => void; onNext: () => void }) {
  const setStatus = async (id: string, status: CatalogStatus) => {
    setCatalog(catalog.map((c) => (c.content_id === id ? { ...c, status } : c)));
    await api.setCatalogStatus(id, status);
  };
  const count = (s: CatalogStatus) => catalog.filter((c) => c.status === s).length;
  const reports = Object.values(
    catalog.reduce<Record<string, CatalogItem[]>>((acc, c) => ({ ...acc, [c.report_id]: [...(acc[c.report_id] ?? []), c] }), {}),
  );
  const riskyForSale = catalog.filter((c) => c.sensitivity === "sensitive" && c.status !== "excluded");

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">Here is what we found on your site</h2>
        <p className="mt-1 text-sm text-muted">
          {reports.length} documents, split into {catalog.length} sections. For each section, choose what AI agents are allowed to do with it.
        </p>
        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          {STATUS_OPTIONS.map((o) => (
            <div key={o.key} className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
              <span className="text-xl">{o.icon}</span>
              <div className="flex-1">
                <div className="text-sm font-semibold">{o.label}</div>
                <div className="text-xs text-muted">{o.help}</div>
              </div>
              <span className="font-mono text-xl font-semibold">{count(o.key)}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 rounded-lg bg-accent/5 px-3 py-2 text-xs text-muted">
          🛡️ Agents only see titles and topics. No figure from your documents is ever shown before payment.
        </p>
      </Card>

      {riskyForSale.length > 0 && (
        <div className="animate-fade-in rounded-xl border border-warn/50 bg-warn/10 p-4 text-sm">
          <span className="font-semibold text-warn">⚠️ {riskyForSale.length === 1 ? "One section looks" : `${riskyForSale.length} sections look`} internal.</span>{" "}
          We recommend keeping {riskyForSale.map((c) => `"${c.title}"`).join(", ")} private.
        </div>
      )}

      {reports.map((sections) => (
        <Card key={sections[0].report_id} title={`📄 ${sections[0].title}`} subtitle={`${sections.length} section${sections.length > 1 ? "s" : ""} · ${sections[0].region} · ${sections[0].period}`}>
          <div className="divide-y divide-border">
            {sections.map((c) => (
              <div key={c.content_id} className="flex flex-col gap-3 py-3 first:pt-0 last:pb-0 md:flex-row md:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.section}</span>
                    {c.sensitivity === "sensitive" && <span className="rounded-full bg-warn/15 px-2 py-0.5 text-xs font-medium text-warn">Looks internal</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {c.data_types.map((d) => (
                      <span key={d} className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted">
                        {humanize(d)}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {c.status === "sellable" && `Agents can buy up to ${TIER_LABEL[c.suggested_tier]} from it.`}
                    {c.status === "free" && "Agents can read it for free."}
                    {c.status === "excluded" && "Hidden from agents, never sold."}
                  </div>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  {STATUS_OPTIONS.map((o) => (
                    <button
                      key={o.key}
                      onClick={() => setStatus(c.content_id, o.key)}
                      title={o.help}
                      className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${c.status === o.key ? o.active : "border-border text-muted hover:bg-surface-2 hover:text-foreground"}`}
                    >
                      {o.icon} {o.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}

      <div className="flex items-center justify-end gap-3">
        <span className="text-sm text-muted">Next: set your prices</span>
        <Button onClick={onNext}>Continue</Button>
      </div>
    </div>
  );
}

function RulesStep({ tiers, setTiers, onNext }: { tiers: Tier[] | null; setTiers: (t: Tier[]) => void; onNext: () => void }) {
  const [text, setText] = useState(mockRulesText);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      setTiers(await api.putRules(text));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const confirm = async () => {
    await api.confirmRules();
    onNext();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Your pricing rules, in plain language">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={9}
          className="w-full rounded-lg border border-border bg-background p-3 text-sm outline-none focus:border-accent"
        />
        <div className="mt-3 flex justify-end">
          <Button onClick={generate} disabled={loading || !text.trim()}>
            {loading ? "Generating tiers…" : "Generate tiers"}
          </Button>
        </div>
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      </Card>
      <Card title="Generated tiers, to confirm">
        {!tiers ? (
          <p className="text-sm text-muted">Tiers appear here. Deterministic checks always use this confirmed table, never the raw text.</p>
        ) : (
          <>
            <div className="space-y-2">
              {tiers.map((t) => (
                <div key={t.tier} className="animate-fade-in flex items-center gap-4 rounded-lg border border-border bg-background p-3">
                  <div className="w-24 text-xl font-semibold">{usdc(t.price_usdc).replace(" USDC", "")}</div>
                  <div className="flex-1">
                    <div className="font-mono text-sm">{t.tier}</div>
                    <div className="text-xs text-muted">{t.scope}</div>
                  </div>
                  <div className="font-mono text-xs text-muted">/query/{t.route}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <Button variant="ok" onClick={confirm}>
                Confirm tiers
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

function ActivateStep() {
  const { address, chainId, isConnected } = useAccount();
  const { connect, connectors, isPending, error: connectError } = useConnect();
  const { disconnect } = useDisconnect();
  const { switchChain } = useSwitchChain();
  const [saved, setSaved] = useState<string | null>(null);
  const [result, setResult] = useState<{ gateway: string; manifest: Manifest } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wrongChain = isConnected && chainId !== baseSepolia.id;

  useEffect(() => {
    if (address && !wrongChain && saved !== address) {
      api.setWallet(address).then(() => setSaved(address), (e) => setError(String(e)));
    }
  }, [address, wrongChain, saved]);

  const doActivate = async () => {
    setError(null);
    try {
      setResult(await api.activate());
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Publisher wallet (Base Sepolia)">
        {!isConnected ? (
          <>
            <p className="mb-4 text-sm text-muted">USDC from every sale goes straight to this wallet.</p>
            <Button onClick={() => connectors[0] && connect({ connector: connectors[0], chainId: baseSepolia.id })} disabled={isPending}>
              {isPending ? "Waiting for MetaMask…" : "Connect MetaMask"}
            </Button>
            {connectError && <p className="mt-3 text-sm text-bad">{connectError.message}</p>}
          </>
        ) : (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <span className="text-ok">●</span>
              <span className="font-mono">{shortHex(address!)}</span>
              <button onClick={() => disconnect()} className="text-xs text-muted hover:text-foreground">
                disconnect
              </button>
            </div>
            {wrongChain ? (
              <Button variant="warn" onClick={() => switchChain({ chainId: baseSepolia.id })}>
                Switch to Base Sepolia
              </Button>
            ) : (
              <p className="text-muted">{saved === address ? "Wallet stored as payTo." : "Saving wallet…"}</p>
            )}
          </div>
        )}
      </Card>
      <Card title="Activate">
        {!result ? (
          <>
            <p className="mb-4 text-sm text-muted">Generates /.well-known/ai-data.json and turns the paid routes on.</p>
            <Button variant="ok" onClick={doActivate} disabled={!saved}>
              Activate
            </Button>
          </>
        ) : (
          <div className="animate-fade-in space-y-3">
            <p className="text-sm text-ok">Live. Your site now sells data to AI agents.</p>
            <div className="text-sm">
              <span className="text-muted">Gateway </span>
              <span className="font-mono">{result.gateway}</span>
            </div>
            <pre className="max-h-72 overflow-auto rounded-lg bg-background p-3 font-mono text-xs">{JSON.stringify(result.manifest, null, 2)}</pre>
          </div>
        )}
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      </Card>
    </div>
  );
}
