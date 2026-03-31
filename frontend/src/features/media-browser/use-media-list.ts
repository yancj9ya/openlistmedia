import { useCallback, useEffect, useState } from 'react';
import { getMediaList } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';
import type { MediaListQuery, MediaListResponseDto } from '../../shared/api/types';

export function useMediaList(query: MediaListQuery) {
  const [data, setData] = useState<MediaListResponseDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshSeed, setRefreshSeed] = useState(0);

  const reload = useCallback(() => setRefreshSeed((value: number) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMediaList(query)
      .then((payload) => {
        if (cancelled) return;
        setData(payload);
      })
      .catch((reason) => {
        if (cancelled) return;
        if (reason instanceof ApiClientError) {
          setError(reason.message);
          return;
        }
        setError('媒体列表加载失败，请检查 API 服务状态。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [query.categoryPath, query.keyword, query.page, query.pageSize, query.type, refreshSeed]);

  return { data, loading, error, reload };
}