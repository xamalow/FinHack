"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { WagmiProvider, createConfig, http, injected } from "wagmi";
import { base, baseSepolia } from "wagmi/chains";
import { IS_MAINNET } from "@/lib/config";

export const CHAIN = IS_MAINNET ? base : baseSepolia;

export const wagmiConfig = createConfig({
  chains: [CHAIN],
  connectors: [injected({ target: "metaMask" })],
  transports: { [base.id]: http(), [baseSepolia.id]: http() },
  ssr: true,
});

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </WagmiProvider>
  );
}
