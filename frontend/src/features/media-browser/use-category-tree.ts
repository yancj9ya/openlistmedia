import { useEffect, useState } from 'react';
import { getCategoryTree } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';
import { toCategoryBrowserModel, type CategoryBrowserModel } from '../../entities/category/model';

const CATEGORY_CACHE_KEY = 'openlistmedia:category-tree-cache';
const CATEGORY_CACHE_TTL_MS = 1000 * 60 * 30;

interface CachedCategoryTreeEntry {
  path: string;
  expiresAt: number;
  data: CategoryBrowserModel;
}

function toCachePath(path?: string | null) {
  return String(path || '/').trim() || '/';
}

function readCategoryCache(path?: string | null) {
  if (typeof window === 'undefined') {
    return null;
  }
  const cachePath = toCachePath(path);
  try {
    const raw = window.localStorage.getItem(CATEGORY_CACHE_KEY);
    if (!raw) {
      console.info('[category-cache] miss', cachePath);
      return null;
    }
    const parsed = JSON.parse(raw) as Record<string, CachedCategoryTreeEntry>;
    const entry = parsed[cachePath];
    if (!entry) {
      console.info('[category-cache] miss', cachePath);
      return null;
    }
    if (entry.expiresAt <= Date.now()) {
      console.info('[category-cache] stale', cachePath);
      delete parsed[cachePath];
      window.localStorage.setItem(CATEGORY_CACHE_KEY, JSON.stringify(parsed));
      return null;
    }
    console.info('[category-cache] hit', cachePath);
    return entry.data;
  } catch {
    console.info('[category-cache] miss', cachePath);
    return null;
  }
}

function writeCategoryCache(path: string | null | undefined, data: CategoryBrowserModel) {
  if (typeof window === 'undefined') {
    return;
  }
  const cachePath = toCachePath(path);
  try {
    const raw = window.localStorage.getItem(CATEGORY_CACHE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, CachedCategoryTreeEntry>) : {};
    parsed[cachePath] = {
      path: cachePath,
      expiresAt: Date.now() + CATEGORY_CACHE_TTL_MS,
      data,
    };
    window.localStorage.setItem(CATEGORY_CACHE_KEY, JSON.stringify(parsed));
    console.info('[category-cache] store', cachePath);
  } catch {
    console.info('[category-cache] store-failed', cachePath);
  }
}

export function clearCategoryTreeCache(path?: string | null) {
  if (typeof window === 'undefined') {
    return;
  }
  const cachePath = toCachePath(path);
  try {
    const raw = window.localStorage.getItem(CATEGORY_CACHE_KEY);
    if (!raw) {
      return;
    }
    const parsed = JSON.parse(raw) as Record<string, CachedCategoryTreeEntry>;
    if (!(cachePath in parsed)) {
      return;
    }
    delete parsed[cachePath];
    window.localStorage.setItem(CATEGORY_CACHE_KEY, JSON.stringify(parsed));
    console.info('[category-cache] clear', cachePath);
  } catch {
    console.info('[category-cache] clear-failed', cachePath);
  }
}

export function useCategoryTree(path?: string | null) {
  const [data, setData] = useState<CategoryBrowserModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshSeed, setRefreshSeed] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const cached = readCategoryCache(path);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    setError(null);
    console.info('[category-cache] fetch', toCachePath(path));
    getCategoryTree(path || undefined)
      .then((payload) => {
        if (cancelled) return;
        const model = toCategoryBrowserModel(payload);
        setData(model);
        writeCategoryCache(path, model);
      })
      .catch((reason) => {
        if (cancelled) return;
        if (reason instanceof ApiClientError) {
          setError(reason.message);
          return;
        }
        setError('分类加载失败，请检查 API 地址与后端服务。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [path, refreshSeed]);

  function reload() {
    clearCategoryTreeCache(path);
    setRefreshSeed((value) => value + 1);
  }

  return { data, loading, error, reload };
}