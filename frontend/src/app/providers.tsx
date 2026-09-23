"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "@/hooks/useAuth";
import { DemoTourProvider } from "@/components/demo/DemoTourProvider";

/**
 * Client-side providers wrapper.
 * Isolates client-only providers from the server root layout so the root
 * layout can remain a server component.
 */
export function Providers({ children }: { children: ReactNode }) {
  // Create a stable QueryClient per session (not per render)
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30 seconds default
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <DemoTourProvider>{children}</DemoTourProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
