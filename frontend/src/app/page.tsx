import Link from "next/link";

const screens = [
  { href: "/onboarding", title: "1. Activate a site", text: "Paste a URL, review the catalog, set prices in plain language, connect a wallet." },
  { href: "/live", title: "2. Watch an agent buy", text: "KYA, negotiation, 402, signature, settlement and on-chain balances in real time." },
  { href: "/dashboard", title: "3. Get paid", text: "Revenue, transactions with explorer links, and a full audit trail per sale." },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-4xl py-16">
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
        Any website. Any AI agent.
        <br />
        <span className="text-accent">Any piece of information. One payment.</span>
      </h1>
      <p className="mt-6 max-w-2xl text-lg text-muted">
        Turn your proprietary content into data that AI agents can discover, negotiate and pay for in stablecoins, in about 60 seconds, with no code.
      </p>
      <div className="mt-12 grid gap-4 sm:grid-cols-3">
        {screens.map((s) => (
          <Link key={s.href} href={s.href} className="rounded-xl border border-border bg-surface p-5 transition hover:border-accent">
            <div className="font-medium">{s.title}</div>
            <p className="mt-2 text-sm text-muted">{s.text}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
