import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCategoryTree } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';
import { toCategoryBrowserModel, type CategoryBrowserModel } from '../../entities/category/model';

const ROOT_KEY = '__root__';

function normalizedKey(path?: string | null) {
  const value = String(path || '').trim();
  return value || ROOT_KEY;
}

export function useCategoryTree(path?: string | null) {
  const queryClient = useQueryClient();
  const key = normalizedKey(path);

  const query = useQuery<CategoryBrowserModel>({
    queryKey: ['category-tree', key],
    queryFn: ({ signal }) => getCategoryTree(path || undefined, signal).then(toCategoryBrowserModel),
  });

  const error = query.isError
    ? query.error instanceof ApiClientError
      ? query.error.message
      : '分类加载失败，请检查 API 地址与后端服务。'
    : null;

  return {
    data: query.data ?? null,
    loading: query.isPending,
    error,
    reload: () => queryClient.invalidateQueries({ queryKey: ['category-tree', key] }),
  };
}
