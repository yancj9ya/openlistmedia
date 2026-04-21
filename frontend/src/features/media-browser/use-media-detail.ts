import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getMediaDetail } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';
import type { MediaDetailDto } from '../../shared/api/types';

export function useMediaDetail(mediaId: number | null) {
  const queryClient = useQueryClient();

  const query = useQuery<MediaDetailDto>({
    queryKey: ['media-detail', mediaId],
    queryFn: ({ signal }) => getMediaDetail(mediaId as number, signal),
    enabled: Boolean(mediaId),
  });

  const error = !mediaId
    ? '缺少媒体 ID。'
    : query.isError
      ? query.error instanceof ApiClientError
        ? query.error.message
        : '媒体详情加载失败。'
      : null;

  return {
    data: query.data ?? null,
    loading: Boolean(mediaId) && query.isPending,
    error,
    reload: () => queryClient.invalidateQueries({ queryKey: ['media-detail', mediaId] }),
  };
}
