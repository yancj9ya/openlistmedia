import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { getMediaList } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';
import type { MediaListQuery, MediaListResponseDto } from '../../shared/api/types';

export function useMediaList(query: MediaListQuery) {
  const queryClient = useQueryClient();

  const queryKey = ['media-list', query] as const;

  const result = useQuery<MediaListResponseDto>({
    queryKey,
    queryFn: ({ signal }) => getMediaList(query, signal),
    placeholderData: keepPreviousData,
  });

  const error = result.isError
    ? result.error instanceof ApiClientError
      ? result.error.message
      : '媒体列表加载失败，请检查 API 服务状态。'
    : null;

  return {
    data: result.data ?? null,
    loading: result.isPending,
    error,
    reload: () => queryClient.invalidateQueries({ queryKey: ['media-list'] }),
  };
}
