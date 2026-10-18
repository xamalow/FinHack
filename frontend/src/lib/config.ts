export const GATEWAY_URL = (process.env.NEXT_PUBLIC_GATEWAY_URL ?? "").replace(/\/$/, "");

// Mocks are on until a gateway URL is set, or when forced with NEXT_PUBLIC_USE_MOCKS=true.
export const USE_MOCKS = !GATEWAY_URL || process.env.NEXT_PUBLIC_USE_MOCKS === "true";

export const EXPLORER_URL = process.env.NEXT_PUBLIC_EXPLORER_URL || "https://sepolia.basescan.org";
export const DEMO_SITE_URL = process.env.NEXT_PUBLIC_DEMO_SITE_URL || "https://demo-research.vercel.app";
export const BUYER_WALLET = process.env.NEXT_PUBLIC_BUYER_WALLET || "0x7a3c5e1b9d04f2a68c3e7b15d9a0e4c2b8f61f21";

export const txUrl = (hash: string) => `${EXPLORER_URL}/tx/${hash}`;
export const addressUrl = (addr: string) => `${EXPLORER_URL}/address/${addr}`;
