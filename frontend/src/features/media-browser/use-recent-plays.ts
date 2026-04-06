import { useEffect, useState } from 'react';
import { getRecentPlayHistory } from '../../shared/api/media-api';
import type { PlayHistoryDto } from '../../shared/api/types';

interface UseRecentPlaysState {
  data: PlayHistoryDto[] | null;
  loading: boolean;
  error: Error | null;
}

export function useRecentPlays() {
  const [state, setState] = useState<UseRecentPlaysState>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let mounted = true;

    async function fetchRecentPlays() {
      try {
        setState((prev) => ({ ...prev, loading: true, error: null }));
        const result = await getRecentPlayHistory();
        if (mounted) {
          setState({ data: result, loading: false, error: null });
        }
      } catch (err) {
        if (mounted) {
          setState({
            data: null,
            loading: false,
            error: err instanceof Error ? err : new Error('Failed to fetch recent plays'),
          });
        }
      }
    }

    fetchRecentPlays();

    return () => {
      mounted = false;
    };
  }, []);

  return state;
}
