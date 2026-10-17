"use client";

import { useEffect, useState } from "react";
import { useAccount, useConnect, useDisconnect, useSwitchChain } from "wagmi";
import { baseSepolia } from "wagmi/chains";
import { Button, Card, shortHex, usdc } from "@/components/ui";
import * as api from "@/lib/api";
import { DEMO_SITE_URL } from "@/lib/config";
import { mockRulesText } from "@/lib/mocks";
import type { CatalogItem, CatalogStatus, Manifest, Tier } from "@/lib/types";
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
          <ul className="mt-4 space-y-1.5 font-mono text-sm">
            {scanEvents.map((e) => (
              <li key={e.event_id ?? e.ts} className="animate-fade-in flex gap-3">
                <span className={e.type === "scan_ready" ? "text-ok" : "text-accent"}>●</span>
                <span className="text-muted">{e.type}</span>
                <span>{e.summary}</span>
              </li>
            ))}
            {!ready && <li className="animate-pulse text-muted">…</li>}
          </ul>
        </div>
      )}
    </Card>
  );
}

const STATUS_STYLE: Record<CatalogStatus, string> = {
  sellable: "bg-accent text-white",
  free: "bg-ok text-black",
  excluded: "bg-bad text-black",
};

function CatalogStep({ catalog, setCatalog, onNext }: { catalog: CatalogItem[]; setCatalog: (c: CatalogItem[]) => void; onNext: () => void }) {
  const setStatus = async (id: string, status: CatalogStatus) => {
    setCatalog(catalog.map((c) => (c.content_id === id ? { ...c, status } : c)));
    await api.setCatalogStatus(id, status);
  };
  const counts = catalog.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.status]: (acc[c.status] ?? 0) + 1 }), {});

  return (
    <Card
      title={`Catalog, ${catalog.length} items`}
      right={
        <span className="text-xs text-muted">
          {counts.sellable ?? 0} sellable · {counts.free ?? 0} free · {counts.excluded ?? 0} excluded
        </span>
      }
    >
      <p className="mb-4 text-sm text-muted">Metadata only. No figure from your paid content ever appears here.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="pb-2 pr-4 font-normal">Report / section</th>
              <th className="pb-2 pr-4 font-normal">Topic</th>
              <th className="pb-2 pr-4 font-normal">Data</th>
              <th className="pb-2 pr-4 font-normal">Tier</th>
              <th className="pb-2 font-normal">Status</th>
            </tr>
          </thead>
          <tbody>
            {catalog.map((c) => (
              <tr key={c.content_id} className="border-t border-border">
                <td className="py-2.5 pr-4">
                  <div>{c.title}</div>
                  <div className="text-xs text-muted">
                    {c.section}
                    {c.sensitivity === "sensitive" && <span className="ml-2 rounded bg-warn/15 px-1.5 text-warn">sensitive</span>}
                  </div>
                </td>
                <td className="pr-4 text-muted">
                  {c.topic} · {c.region} · {c.period}
                </td>
                <td className="pr-4 text-xs text-muted">{c.data_types.join(", ")}</td>
                <td className="pr-4 font-mono text-xs">{c.suggested_tier}</td>
                <td>
                  <div className="inline-flex overflow-hidden rounded-lg border border-border">
                    {(["sellable", "free", "excluded"] as CatalogStatus[]).map((s) => (
                      <button
                        key={s}
                        onClick={() => setStatus(c.content_id, s)}
                        className={`px-2.5 py-1 text-xs ${c.status === s ? STATUS_STYLE[s] : "text-muted hover:bg-surface-2"}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex justify-end">
        <Button onClick={onNext}>Continue</Button>
      </div>
    </Card>
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
