/**
 * React Query Provider
 * Wraps the app with React Query client for data fetching and caching
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { ErrorTracker } from '../../lib/debug';

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30000, // 30 seconds
            retry: (failureCount: number, error: unknown) => {
              // Don't retry on 4xx errors
              if (error instanceof Error && 'statusCode' in error) {
                const statusCode = (error as { statusCode: number }).statusCode;
                if (statusCode >= 400 && statusCode < 500) {
                  return false;
                }
              }
              return failureCount < 2;
            },
            refetchOnWindowFocus: false,
            refetchOnReconnect: true,
          },
          mutations: {
            retry: 1,
            onError: (error: unknown) => {
              ErrorTracker.captureException(error instanceof Error ? error : new Error(String(error)));
            },
          },
        },
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

