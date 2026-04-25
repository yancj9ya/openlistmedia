import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useMemo } from 'react';
import { AppProviders } from './providers';
import { AppRouter } from './router';

export function App() {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60 * 5,
            gcTime: 1000 * 60 * 30,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
    [],
  );
  return (
    <QueryClientProvider client={queryClient}>
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </QueryClientProvider>
  );
}