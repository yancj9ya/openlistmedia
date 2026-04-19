import { useQuery } from '@tanstack/react-query';
import { getRecentPlayHistory } from '../../shared/api/media-api';
import type { PlayHistoryDto } from '../../shared/api/types';

export function useRecentPlays() {
  const query = useQuery<PlayHistoryDto[]>({
    queryKey: ['recent-plays'],
    queryFn: ({ signal }) => getRecentPlayHistory(signal),
  });

  return {
    data: query.data ?? null,
    loading: query.isPending,
    error: query.isError ? (query.error instanceof Error ? query.error : new Error('Failed to fetch recent plays')) : null,
  };
}
