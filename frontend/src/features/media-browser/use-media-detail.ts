import { useCallback, useEffect, useState } from 'react';
import { getMediaDetail } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';
import type { MediaDetailDto } from '../../shared/api/types';

export function useMediaDetail(mediaId: number | null) {
  const [data, setData] = useState<MediaDetailDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
    setReloadToken((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!mediaId) {
      setData(null);
      setLoading(false);
      setError('缺少媒体 ID。');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMediaDetail(mediaId)
      .then((payload) => {
        if (cancelled) return;
        setData(payload);
      })
      .catch((reason) => {
        if (cancelled) return;
        setData(null);
        if (reason instanceof ApiClientError) {
          setError(reason.message);
          return;
        }
        setError('媒体详情加载失败。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mediaId, reloadToken]);

  return { data, loading, error, reload };
}