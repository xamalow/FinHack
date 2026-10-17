import { addressUrl, txUrl } from "@/lib/config";

export function Card({ title, children, className = "", right }: { title?: string; children: React.ReactNode; className?: string; right?: React.ReactNode }) {
  return (
    <section className={`rounded-xl border border-border bg-surface ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-medium">{title}</h2>
          {right}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "ok" | "warn" }) {
  const styles = {
    primary: "bg-accent text-white hover:brightness-110",
    ghost: "border border-border text-foreground hover:bg-surface-2",
    ok: "bg-ok text-black hover:brightness-110",
    warn: "bg-warn text-black hover:brightness-110",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export const shortHex = (h: string, head = 6, tail = 4) => (h.length > head + tail + 1 ? `${h.slice(0, head)}…${h.slice(-tail)}` : h);

export function TxLink({ hash }: { hash: string }) {
  return (
    <a href={txUrl(hash)} target="_blank" rel="noreferrer" className="font-mono text-accent hover:underline">
      {shortHex(hash, 10, 6)} ↗
    </a>
  );
}

export function AddressLink({ address }: { address: string }) {
  return (
    <a href={addressUrl(address)} target="_blank" rel="noreferrer" className="font-mono text-accent hover:underline">
      {shortHex(address)}
    </a>
  );
}

export const usdc = (n: number) => `${n.toFixed(2)} USDC`;
export const atomicToUsdc = (a: string | number) => Number(a) / 1e6;
