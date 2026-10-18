"use client";

import { useEffect, useState } from "react";
import { useAccount, useConnect, useDisconnect, useSwitchChain } from "wagmi";
import { baseSepolia } from "wagmi/chains";
import Link from "next/link";
import { Button, Card, shortHex } from "@/components/ui";
import * as api from "@/lib/api";
import { DEMO_SITE_URL } from "@/lib/config";
import { mockRulesText } from "@/lib/mocks";
import type { CatalogItem, CatalogStatus, Manifest, Tier } from "@/lib/types";
import { labelFor } from "@/lib/eventLabels";
import { useEventStream } from "@/lib/useEventStream";

const STEPS = ["Website", "Content", "Prices", "Go live"];
const SCAN_STAGES = ["scan_started", "scan_extracting", "scan_indexing", "scan_ready"];

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [tiers, setTiers] = useState<Tier[] | null>(null);

  return (
    <div className="mx-auto max-w-3xl">
      <ol className="mb-8 flex items-center justify-center gap-2 text-sm">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2">
            {i > 0 && <span className="h-px w-6 bg-border" />}
            <button
              onClick={() => i < step && setStep(i)}
              className={`flex items-center gap-1.5 ${i === step ? "font-semibold text-foreground" : i < step ? "text-ok" : "text-muted"}`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${i === step ? "bg-accent text-white" : i < step ? "bg-ok text-white" : "bg-surface-2"}`}
              >
                {i < step ? "✓" : i + 1}
              </span>
              <span className="hidden sm:inline">{s}</span>
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

function StepTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="mb-5 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 text-muted">{sub}</p>
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
  const last = scanEvents.at(-1);

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
    <>
      <StepTitle title="Sell your data to AI agents" sub="Paste your website. We find what can be sold." />
      <Card>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2.5 outline-none focus:border-accent"
            placeholder="https://your-site.com"
          />
          <Button onClick={start} disabled={scanning || !url}>
            {scanning ? "Scanning…" : "Scan"}
          </Button>
        </div>
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
        {scanning && (
          <div className="mt-5">
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full bg-accent transition-all duration-700" style={{ width: `${((stage + 1) / SCAN_STAGES.length) * 100}%` }} />
            </div>
            <p key={String(last?.event_id)} className={`animate-fade-in mt-3 text-sm ${ready ? "text-ok" : "text-muted"}`}>
              {last ? `${labelFor(last.type).icon} ${labelFor(last.type).title}` : "Starting…"}
            </p>
          </div>
        )}
      </Card>
    </>
  );
}

const STATUS_OPTIONS: { key: CatalogStatus; label: string; active: string }[] = [
  { key: "sellable", label: "Sell", active: "bg-accent text-white" },
  { key: "free", label: "Free", active: "bg-ok text-white" },
  { key: "excluded", label: "Private", active: "bg-bad text-white" },
];

// P1 marks the scanned internal page "internal"; the mock catalog uses "sensitive".
const isInternal = (c: CatalogItem) => c.sensitivity === "internal" || c.sensitivity === "sensitive";

function CatalogStep({ catalog, setCatalog, onNext }: { catalog: CatalogItem[]; setCatalog: (c: CatalogItem[]) => void; onNext: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const setStatus = async (id: string, status: CatalogStatus) => {
    const before = catalog;
    setError(null);
    setCatalog(catalog.map((c) => (c.content_id === id ? { ...c, status } : c)));
    try {
      await api.setCatalogStatus(id, status);
    } catch {
      setCatalog(before);
      setError("Internal pages stay private.");
    }
  };
  const count = (s: CatalogStatus) => catalog.filter((c) => c.status === s).length;
  const reports = Object.values(
    catalog.reduce<Record<string, CatalogItem[]>>((acc, c) => ({ ...acc, [c.report_id]: [...(acc[c.report_id] ?? []), c] }), {}),
  );

  return (
    <>
      <StepTitle title="What can agents buy?" sub="Agents only see titles. Never a number before they pay." />
      <div className="mb-4 flex justify-center gap-4 text-sm">
        <span>
          <b>{count("sellable")}</b> <span className="text-muted">for sale</span>
        </span>
        <span>
          <b>{count("free")}</b> <span className="text-muted">free</span>
        </span>
        <span>
          <b>{count("excluded")}</b> <span className="text-muted">private</span>
        </span>
      </div>
      {error && <p className="mb-3 text-center text-sm text-bad">🔒 {error}</p>}

      <div className="space-y-3">
        {reports.map((sections) => (
          <Card key={sections[0].report_id}>
            <div className="mb-2 text-sm font-semibold">📄 {sections[0].title}</div>
            <div className="divide-y divide-border">
              {sections.map((c) => (
                <div key={c.content_id} className="flex items-center gap-3 py-2">
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {c.section}
                    {isInternal(c) && <span className="ml-2 rounded-full bg-warn/15 px-2 py-0.5 text-xs text-warn">internal</span>}
                  </span>
                  <div className="inline-flex shrink-0 overflow-hidden rounded-lg border border-border text-xs">
                    {STATUS_OPTIONS.map((o) => (
                      <button
                        key={o.key}
                        onClick={() => setStatus(c.content_id, o.key)}
                        className={`px-3 py-1.5 font-medium transition ${c.status === o.key ? o.active : "text-muted hover:bg-surface-2"}`}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={onNext}>Continue</Button>
      </div>
    </>
  );
}

const TIER_NAME: Record<string, string> = {
  single_fact: "One figure",
  small_table: "Small table",
  full_section: "Full section",
};

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
    <>
      <StepTitle title="Set your prices" sub="Write your rules in plain words. We turn them into prices." />
      <Card>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          className="w-full rounded-lg border border-border bg-background p-3 text-sm outline-none focus:border-accent"
        />
        {error && <p className="mt-2 text-sm text-bad">{error}</p>}
        {!tiers && (
          <div className="mt-3 flex justify-end">
            <Button onClick={generate} disabled={loading || !text.trim()}>
              {loading ? "Reading your rules…" : "Create prices"}
            </Button>
          </div>
        )}
      </Card>

      {tiers && (
        <div className="animate-fade-in mt-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {tiers.map((t) => (
              <div key={t.tier} className="rounded-xl border border-border bg-surface p-4 text-center shadow-sm">
                <div className="text-3xl font-semibold">${t.price_usdc.toFixed(2)}</div>
                <div className="mt-1 font-medium">{TIER_NAME[t.tier] ?? t.tier}</div>
                <div className="mt-1 text-xs text-muted">{t.scope}</div>
              </div>
            ))}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={generate} disabled={loading}>
              Redo
            </Button>
            <Button onClick={confirm}>Looks good</Button>
          </div>
        </div>
      )}
    </>
  );
}

function ActivateStep() {
  const { address, chainId, isConnected } = useAccount();
  const { connect, connectors, isPending, error: connectError } = useConnect();
  const { disconnect } = useDisconnect();
  const { switchChain } = useSwitchChain();
  const [manual, setManual] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [result, setResult] = useState<{ gateway: string; manifest: Manifest } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wrongChain = isConnected && chainId !== baseSepolia.id;

  const save = (w: string) => api.setWallet(w).then(() => setSaved(w), (e) => setError(String(e)));

  useEffect(() => {
    if (address && !wrongChain && saved !== address) void save(address);
  }, [address, wrongChain, saved]);

  const doActivate = async () => {
    setError(null);
    try {
      setResult(await api.activate());
    } catch (e) {
      setError(String(e));
    }
  };

  if (result) {
    return (
      <div className="animate-fade-in text-center">
        <div className="text-5xl">🎉</div>
        <h1 className="mt-3 text-2xl font-semibold">Your site is live</h1>
        <p className="mt-1 text-muted">AI agents can now find and buy your data. You get paid in USDC.</p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/live" className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:brightness-110">
            Watch agents buy
          </Link>
          <Link href="/dashboard" className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-surface-2">
            Dashboard
          </Link>
        </div>
        <details className="mx-auto mt-8 max-w-xl text-left text-sm">
          <summary className="cursor-pointer text-center text-muted">Technical details</summary>
          <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-surface-2 p-3 font-mono text-xs">{JSON.stringify(result.manifest, null, 2)}</pre>
        </details>
      </div>
    );
  }

  return (
    <>
      <StepTitle title="Go live" sub="Choose where your money goes, then switch on." />
      <Card>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-sm ${saved ? "bg-ok text-white" : "bg-surface-2"}`}>{saved ? "✓" : "1"}</span>
            <div className="flex-1">
              {saved ? (
                <span className="text-sm">
                  Paid to <span className="font-mono">{shortHex(saved)}</span>
                  {isConnected && (
                    <button onClick={() => { disconnect(); setSaved(null); }} className="ml-2 text-xs text-muted hover:text-foreground">
                      change
                    </button>
                  )}
                </span>
              ) : wrongChain ? (
                <Button variant="warn" onClick={() => switchChain({ chainId: baseSepolia.id })}>
                  Switch to Base Sepolia
                </Button>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <Button onClick={() => connectors[0] && connect({ connector: connectors[0], chainId: baseSepolia.id })} disabled={isPending}>
                    {isPending ? "Check MetaMask…" : "Connect wallet"}
                  </Button>
                  <span className="text-xs text-muted">or</span>
                  <input
                    value={manual}
                    onChange={(e) => setManual(e.target.value.trim())}
                    placeholder="paste an address 0x…"
                    className="w-56 rounded-lg border border-border bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-accent"
                  />
                  {/^0x[0-9a-fA-F]{40}$/.test(manual) && (
                    <Button variant="ghost" onClick={() => save(manual)}>
                      Use
                    </Button>
                  )}
                </div>
              )}
              {connectError && !saved && <p className="mt-2 text-xs text-bad">{connectError.message}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-2 text-sm">2</span>
            <Button variant="ok" onClick={doActivate} disabled={!saved}>
              Go live
            </Button>
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
      </Card>
    </>
  );
}
