"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { USE_MOCKS } from "@/lib/config";
import { Logo } from "@/components/Logo";

const links = [
  { href: "/onboarding", label: "Onboarding" },
  { href: "/live", label: "Live view" },
  { href: "/dashboard", label: "Dashboard" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-4 py-3 sm:px-6">
        <Link href="/">
          <Logo />
        </Link>
        <nav className="flex gap-1 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-1.5 transition ${path.startsWith(l.href) ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground"}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        {USE_MOCKS && (
          <span className="ml-auto rounded-full border border-warn/40 px-2.5 py-0.5 text-xs text-warn" title="Set NEXT_PUBLIC_GATEWAY_URL to use the real gateway">
            mock data
          </span>
        )}
      </div>
    </header>
  );
}
