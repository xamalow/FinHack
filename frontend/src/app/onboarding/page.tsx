"use client";

import { useEffect, useRef, useState } from "react";
import { useAccount, useConnect, useDisconnect, useSwitchChain } from "wagmi";
import { CHAIN } from "@/app/providers";
import { CHAIN_NAME } from "@/lib/config";
import Link from "next/link";
import { Button, Card, shortHex } from "@/components/ui";
import * as api from "@/lib/api";
import { DEMO_SITE_URL } from "@/lib/config";
import { mockRulesText } from "@/lib/mocks";
import type { CatalogItem, CatalogStatus, Manifest, Tier } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";

const STEPS = ["Website", "Content", "Prices", "Go live"];

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

type ScanState = "pending" | "running" | "done" | "failed";

// The scan, as four steps with live timings. Each step starts with the first event of its stage (P1's crawler
// emits scan_started, one scan_extracting per document, one scan_indexing per catalog item, then scan_ready).
const SCAN_STEPS = [
  { key: "scan_started", name: "Reading your site", detail: "Sitemap and robots.txt, like a search engine" },
  { key: "scan_extracting", name: "Extracting pages and reports", detail: "Text from every page and PDF" },
  { key: "scan_indexing", name: "Cutting it into sellable pieces", detail: "Each section gets a topic, a period and a price tier" },
  { key: "scan_ready", name: "Catalog ready", detail: "Nothing is for sale until you say so" },
];

function ScanStep({ onDone }: { onDone: () => void }) {
  const [url, setUrl] = useState(DEMO_SITE_URL);
  const [scanning, setScanning] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const { events } = useEventStream();
  const [since, setSince] = useState(0);
  const scanEvents = events.slice(since).filter((e) => e.actor === "publisher" && e.type.startsWith("scan_"));
  const firstAt = (type: string) => {
    const e = scanEvents.find((x) => x.type === type);
    return e ? Date.parse(e.ts) : null;
  };
  const failed = scanEvents.find((e) => e.type === "scan_failed");
  const ready = scanEvents.find((e) => e.type === "scan_ready");
  const starts = SCAN_STEPS.map((s, i) => firstAt(s.key) ?? (i === 0 && scanning ? startedAt : null));
  const extracted = scanEvents.filter((e) => e.type === "scan_extracting" && e.payload.kind);
  const indexed = scanEvents.filter((e) => e.type === "scan_indexing");
  const pdfs = extracted.filter((e) => e.payload.kind === "pdf").length;
  const lastTitle = (list: typeof scanEvents) => String(list.at(-1)?.payload.title ?? list.at(-1)?.summary ?? "");

  const steps = SCAN_STEPS.map((s, i) => {
    const begin = starts[i];
    const next = starts.slice(i + 1).find((x) => x !== null) ?? null;
    let state: ScanState = "pending";
    if (begin !== null) state = next !== null || (s.key === "scan_ready" && ready) ? "done" : "running";
    if (failed && state === "running") state = "failed";
    const end = state === "done" ? (next ?? begin) : null;
    const secs = begin === null ? null : ((end ?? (failed ? Date.parse(failed.ts) : now)) - begin) / 1000;
    let note = "";
    if (s.key === "scan_started" && begin !== null) note = new URL(url).host;
    if (s.key === "scan_extracting" && extracted.length)
      note = state === "done" ? `${extracted.length} documents, ${pdfs} of them PDF reports` : `${extracted.length} documents · ${lastTitle(extracted)}`;
    if (s.key === "scan_indexing" && indexed.length)
      note = state === "done" ? `${indexed.length} sections` : `${indexed.length} sections · ${String(indexed.at(-1)?.summary ?? "").replace(/^Indexed /, "")}`;
    if (s.key === "scan_ready" && ready)
      note = `${ready.payload.sellable ?? "?"} for sale · ${ready.payload.free ?? "?"} free · ${ready.payload.excluded ?? "?"} private`;
    if (state === "failed") note = String(failed?.payload.error ?? failed?.summary ?? "Scan failed");
    return { ...s, state, secs: s.key === "scan_ready" ? null : secs, note };
  });
  const doneCount = steps.filter((s) => s.state === "done").length;
  const total = startedAt === null ? 0 : (((ready ? Date.parse(ready.ts) : failed ? Date.parse(failed.ts) : now) - startedAt) / 1000);

  useEffect(() => {
    if (!scanning || ready || failed) return;
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [scanning, ready, failed]);

  useEffect(() => {
    if (ready) {
      const t = setTimeout(onDone, 1600);
      return () => clearTimeout(t);
    }
  }, [ready, onDone]);

  useEffect(() => {
    if (failed) setScanning(false);
  }, [failed]);

  const start = async () => {
    setError(null);
    setSince(events.length);
    setStartedAt(Date.now());
    setNow(Date.now());
    setScanning(true);
    try {
      await api.scan(url);
    } catch (e) {
      setError(String(e));
      setScanning(false);
      setStartedAt(null);
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
          <Button onClick={start} disabled={(scanning && !failed) || !url}>
            {scanning && !failed ? "Scanning…" : failed ? "Scan again" : "Scan"}
          </Button>
        </div>
        {error && <p className="mt-3 text-sm text-bad">{error}</p>}
        {startedAt !== null && (
          <div className="animate-fade-in mt-6">
            <div className="mb-3 flex items-baseline justify-between text-[13px]">
              <span className="text-muted">{ready ? "Scanned" : failed ? "Stopped" : "Scanning your site"}</span>
              <span className="tabular-nums text-muted">
                {doneCount} of {steps.length} · {total.toFixed(1)} s
              </span>
            </div>
            <div className="mb-4 h-[2px] overflow-hidden rounded-full bg-surface-2">
              <div
                className={`h-full transition-[width] duration-500 ease-out ${failed ? "bg-bad" : ready ? "bg-ok" : "bg-accent"}`}
                style={{ width: `${(doneCount / steps.length) * 100}%` }}
              />
            </div>
            <ol className="space-y-1">
              {steps.map((s, i) => (
                <li
                  key={s.key}
                  className={`grid min-h-[56px] grid-cols-[28px_1fr] gap-x-1 rounded-lg px-1 py-1.5 transition-[opacity,background-color] duration-200 ${
                    s.state === "running" ? "bg-surface-2" : ""
                  } ${s.state === "pending" ? "opacity-45" : ""}`}
                >
                  <span className="grid h-6 place-items-center">
                    {s.state === "done" ? (
                      <span className="text-sm text-ok">✓</span>
                    ) : s.state === "running" ? (
                      <span className="size-1.5 animate-pulse rounded-full bg-accent" />
                    ) : s.state === "failed" ? (
                      <span className="text-[15px] text-bad">×</span>
                    ) : (
                      <span className="tabular-nums text-sm text-muted">{i + 1}</span>
                    )}
                  </span>
                  <div className="min-w-0 pr-2">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[15px] leading-6">{s.name}</span>
                      <span className={`shrink-0 tabular-nums text-xs ${s.state === "failed" ? "text-bad" : "text-muted"}`}>
                        {s.state === "failed"
                          ? "Stopped"
                          : s.state === "done" && s.secs !== null
                            ? `${Math.max(s.secs, 0.1).toFixed(1)} s`
                            : s.state === "running" && s.secs !== null
                              ? `${Math.max(s.secs, 0).toFixed(1)} s`
                              : ""}
                      </span>
                    </div>
                    <div
                      key={s.note}
                      className={`animate-fade-in truncate text-[13px] leading-snug ${
                        s.state === "failed" ? "text-bad" : s.state === "done" && s.key === "scan_ready" ? "text-ok" : s.note ? "text-foreground/70" : "text-muted"
                      }`}
                    >
                      {s.state !== "pending" && s.note ? s.note : s.detail}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
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
  const [previewId, setPreviewId] = useState<string | null>(null);
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
            <ArticleTitle sections={sections} />
            <div className="divide-y divide-border">
              {sections.map((c) => (
                <div key={c.content_id} className={`group flex items-center gap-3 py-2 ${previewId === c.content_id ? "rounded-md bg-accent/5" : ""}`}>
                  <button
                    onClick={() => setPreviewId(c.content_id)}
                    title="Preview this section"
                    className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm"
                  >
                    <span className="truncate group-hover:text-accent">{c.section}</span>
                    {isInternal(c) && <span className="shrink-0 rounded-full bg-warn/15 px-2 py-0.5 text-xs text-warn">internal</span>}
                    <span
                      className={`grid size-6 shrink-0 place-items-center rounded-md transition ${
                        previewId === c.content_id ? "bg-accent/10 text-accent" : "text-muted/60 group-hover:bg-surface-2 group-hover:text-accent"
                      }`}
                    >
                      <EyeIcon />
                    </span>
                  </button>
                  <StatusToggle value={c.status} onChange={(s) => setStatus(c.content_id, s)} />
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={onNext}>Continue</Button>
      </div>

      {previewId && (
        <PreviewDrawer
          items={reports.flat()}
          id={previewId}
          onMove={setPreviewId}
          onStatus={setStatus}
          onClose={() => setPreviewId(null)}
        />
      )}
    </>
  );
}

// The page an article was scanned from: its free HTML page when there is one, else the PDF.
function articleUrls(sections: CatalogItem[]): { page: string | null; pdf: string | null } {
  const urls = sections.map((s) => s.source_url).filter((u): u is string => !!u);
  return { page: urls.find((u) => !/\.pdf($|\?)/i.test(u)) ?? null, pdf: urls.find((u) => /\.pdf($|\?)/i.test(u)) ?? null };
}

// Report title with a hover card: a live miniature of the real page, its address and links. Takes no room in the list.
function ArticleTitle({ sections }: { sections: CatalogItem[] }) {
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { page, pdf } = articleUrls(sections);
  const url = page ?? pdf;
  const show = (on: boolean) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setOpen(on), on ? 250 : 150);
  };
  const title = sections.find((s) => s.section !== "Free article")?.title ?? sections[0].title;
  const sellable = sections.filter((s) => s.status === "sellable").length;
  if (!url) return <div className="mb-2 text-sm font-semibold">📄 {title}</div>;
  const short = url.replace(/^https?:\/\//, "");

  return (
    <div className="relative mb-2" onMouseEnter={() => show(true)} onMouseLeave={() => show(false)}>
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        onFocus={() => show(true)}
        onBlur={() => show(false)}
        className="group inline-flex max-w-full items-center gap-1.5 text-sm font-semibold hover:text-accent"
      >
        <span className="truncate">📄 {title}</span>
        <span className="text-muted/60 transition group-hover:text-accent" aria-hidden="true">↗</span>
      </a>
      {open && (
        <div className="animate-fade-in absolute left-0 top-full z-30 mt-2 w-[300px] overflow-hidden rounded-xl border border-border bg-surface shadow-xl">
          <div className="relative h-[170px] overflow-hidden border-b border-border bg-surface-2">
            {page ? (
              <iframe
                src={page}
                title={`Preview of ${title}`}
                loading="lazy"
                tabIndex={-1}
                sandbox=""
                className="pointer-events-none absolute left-0 top-0 h-[773px] w-[1364px] origin-top-left scale-[0.22]"
              />
            ) : (
              <div className="grid h-full place-items-center text-4xl">📄</div>
            )}
          </div>
          <div className="space-y-1 p-3">
            <div className="line-clamp-2 text-sm font-semibold leading-snug">{title}</div>
            <div className="truncate text-xs text-muted">{short}</div>
            <div className="flex items-center justify-between pt-1 text-xs">
              <span className="text-muted">
                {sections.length} section{sections.length > 1 ? "s" : ""} · {sellable} for sale
              </span>
              <span className="flex gap-3">
                {page && (
                  <a href={page} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                    Article ↗
                  </a>
                )}
                {pdf && (
                  <a href={pdf} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                    PDF ↗
                  </a>
                )}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusToggle({ value, onChange }: { value: CatalogStatus; onChange: (s: CatalogStatus) => void }) {
  return (
    <div className="inline-flex shrink-0 overflow-hidden rounded-lg border border-border text-xs">
      {STATUS_OPTIONS.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-3 py-1.5 font-medium transition ${value === o.key ? o.active : "text-muted hover:bg-surface-2"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function EyeIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// Figures are what agents pay for: the preview marks them so the publisher sees what stays behind the paywall.
function withFigures(text: string) {
  return text.split(/(\d+(?:[.,]\d+)*(?:\s?(?:%|GWh|MWh|GW|USD|EUR|€|bn)\b|%)?)/g).map((part, i) =>
    i % 2 && !/^(19|20)\d\d$/.test(part) ? (
      <mark key={i} className="rounded bg-accent/10 px-0.5 font-medium text-foreground">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

type Preview = { text: string } | { error: string } | null;

function PreviewDrawer({
  items,
  id,
  onMove,
  onStatus,
  onClose,
}: {
  items: CatalogItem[];
  id: string;
  onMove: (id: string) => void;
  onStatus: (id: string, s: CatalogStatus) => void;
  onClose: () => void;
}) {
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const index = items.findIndex((c) => c.content_id === id);
  const item = items[index];
  const preview = previews[id] ?? null;

  useEffect(() => {
    if (id in previews) return;
    let alive = true;
    api.getPreview(id).then(
      (p) => alive && setPreviews((m) => ({ ...m, [id]: { text: p.text } })),
      () => alive && setPreviews((m) => ({ ...m, [id]: { error: "No text stored for this section yet. Run a scan first." } })),
    );
    return () => {
      alive = false;
    };
  }, [id, previews]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown" && index < items.length - 1) onMove(items[index + 1].content_id);
      if (e.key === "ArrowUp" && index > 0) onMove(items[index - 1].content_id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, items, onMove, onClose]);

  if (!item) return null;
  const meta = [item.topic, item.region, item.period].filter(Boolean).join(" · ");
  return (
    <div className="animate-fade-in fixed inset-0 z-50 flex justify-end bg-black/20" onClick={onClose}>
      <aside
        className="animate-slide-in flex h-full w-full max-w-lg flex-col border-l border-border bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs text-muted">📄 {item.title}</div>
            <h2 className="mt-0.5 text-lg font-semibold leading-snug">{item.section}</h2>
            {meta && <div className="mt-1 text-xs text-muted">{meta}</div>}
          </div>
          <div className="flex shrink-0 items-center gap-1 text-muted">
            <button
              onClick={() => index > 0 && onMove(items[index - 1].content_id)}
              disabled={index <= 0}
              title="Previous (↑)"
              className="grid size-7 place-items-center rounded-md hover:bg-surface-2 disabled:opacity-30"
            >
              ↑
            </button>
            <button
              onClick={() => index < items.length - 1 && onMove(items[index + 1].content_id)}
              disabled={index >= items.length - 1}
              title="Next (↓)"
              className="grid size-7 place-items-center rounded-md hover:bg-surface-2 disabled:opacity-30"
            >
              ↓
            </button>
            <button onClick={onClose} title="Close (Esc)" className="grid size-7 place-items-center rounded-md hover:bg-surface-2 hover:text-foreground">
              ✕
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {preview === null ? (
            <div className="space-y-2.5">
              {[92, 100, 85, 97, 60].map((w, i) => (
                <div key={i} className="h-3 animate-pulse rounded bg-surface-2" style={{ width: `${w}%` }} />
              ))}
            </div>
          ) : "error" in preview ? (
            <p className="text-sm text-muted">{preview.error}</p>
          ) : (
            <div key={id} className="animate-fade-in whitespace-pre-wrap text-[14px] leading-relaxed text-foreground/85">
              {withFigures(preview.text)}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
          <span className="text-xs text-muted">Only you see this. Agents see the title until they pay.</span>
          <StatusToggle value={item.status} onChange={(s) => onStatus(item.content_id, s)} />
        </footer>
      </aside>
    </div>
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
  const wrongChain = isConnected && chainId !== CHAIN.id;

  const save = (w: string) => api.setWallet(w).then(() => setSaved(w), (e) => setError(String(e)));

  // Cuts the link with MetaMask for real (its "connected sites" permission), not only in this page,
  // so the next Connect shows the account picker again. The payout wallet already saved is left as is.
  const disconnectWallet = async () => {
    try {
      const eth = (window as unknown as { ethereum?: { request: (a: { method: string; params: unknown[] }) => Promise<unknown> } }).ethereum;
      await eth?.request({ method: "wallet_revokePermissions", params: [{ eth_accounts: {} }] });
    } catch {
      // older MetaMask: the page-side disconnect below still applies
    }
    disconnect();
    setSaved(null);
  };

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
                    <button onClick={disconnectWallet} className="ml-2 text-xs text-muted hover:text-foreground">
                      change
                    </button>
                  )}
                </span>
              ) : wrongChain ? (
                <div className="flex flex-wrap items-center gap-3">
                  <Button variant="warn" onClick={() => switchChain({ chainId: CHAIN.id })}>
                    Switch to {CHAIN_NAME}
                  </Button>
                  <span className="font-mono text-xs text-muted">{address && shortHex(address)}</span>
                  <button onClick={disconnectWallet} className="text-xs text-muted underline hover:text-foreground">
                    Disconnect wallet
                  </button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <Button onClick={() => connectors[0] && connect({ connector: connectors[0], chainId: CHAIN.id })} disabled={isPending}>
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
