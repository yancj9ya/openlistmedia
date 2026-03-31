import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../app/providers';
import { MediaCard } from '../entities/media/media-card';
import { useCategoryTree } from '../features/media-browser/use-category-tree';
import { useMediaList } from '../features/media-browser/use-media-list';
import { ApiClientError } from '../shared/api/client';
import { refreshCategory } from '../shared/api/media-api';
import type { MediaListItemDto } from '../shared/api/types';
import { AsyncState } from '../shared/ui/async-state';

const DEFAULT_PAGE_SIZE = 20;

export function MediaListPage() {
  const { isAdmin } = useAuth();
  const [searchParams] = useSearchParams();
  const categoryPath = searchParams.get('category_path') || undefined;
  const keyword = searchParams.get('keyword') || undefined;
  const type = searchParams.get('type') || undefined;
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<MediaListItemDto[]>([]);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const pageSize = DEFAULT_PAGE_SIZE;
  const query = useMemo(
    () => ({ categoryPath, includeDescendants: Boolean(categoryPath), keyword, type, page, pageSize }),
    [categoryPath, keyword, page, pageSize, type],
  );
  const { data, loading, error, reload: reloadMediaList } = useMediaList(query);
  const { data: rootCategories } = useCategoryTree();
  const topLevelPath = useMemo(() => {
    const rootChildren = rootCategories?.children || [];
    if (!categoryPath) {
      return rootChildren[0]?.path;
    }
    const matched = rootChildren.find((item) => categoryPath === item.path || categoryPath.startsWith(`${item.path}/`));
    return matched?.path || rootChildren[0]?.path;
  }, [categoryPath, rootCategories]);
  const { data: secondaryCategories, reload: reloadSecondaryCategories } = useCategoryTree(topLevelPath);
  const secondaryItems = secondaryCategories?.children || [];
  const [refreshingCategory, setRefreshingCategory] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const years = useMemo(() => {
    const values = new Set<number>();
    items.forEach((item) => {
      const value = Number(item.year || 0);
      if (value > 0) {
        values.add(value);
      }
    });
    return Array.from(values).sort((left, right) => right - left);
  }, [items]);
  const visibleItems = useMemo(() => {
    if (!selectedYear) {
      return items;
    }
    return items.filter((item) => Number(item.year || 0) === selectedYear);
  }, [items, selectedYear]);
  const hasNext = Boolean(data?.pagination.has_next);
  const currentSecondaryPath = categoryPath && categoryPath !== topLevelPath ? categoryPath : null;

  useEffect(() => {
    setSelectedYear(null);
    setPage(1);
    setItems([]);
  }, [categoryPath, keyword, type]);

  useEffect(() => {
    if (!data?.items) {
      return;
    }
    setItems((current) => {
      if (page === 1) {
        return data.items;
      }
      const existingIds = new Set(current.map((item) => item.id));
      const merged = [...current];
      data.items.forEach((item) => {
        if (!existingIds.has(item.id)) {
          merged.push(item);
        }
      });
      return merged;
    });
  }, [data, page]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || !hasNext || loading) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry?.isIntersecting) {
          setPage((current) => current + 1);
        }
      },
      { rootMargin: '240px 0px' },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasNext, loading, items.length]);

  async function handleRefreshSecondaryCategory() {
    if (!currentSecondaryPath || refreshingCategory) {
      return;
    }
    try {
      setRefreshingCategory(true);
      setRefreshMessage(null);
      await refreshCategory(currentSecondaryPath);
      reloadSecondaryCategories();
      reloadMediaList();
      setItems([]);
      setPage(1);
      setRefreshMessage('当前二级分类目录缓存已刷新。');
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setRefreshMessage(reason.message);
        return;
      }
      setRefreshMessage('二级分类缓存刷新失败，请稍后重试。');
    } finally {
      setRefreshingCategory(false);
    }
  }

  return (
    <section className="media-shell">
      <aside className="media-sidebar panel">
        <Link to="/media" className="media-sidebar-title">
          影视海报墙
        </Link>
        <p className="media-sidebar-subtitle">openlist</p>
        <div className="media-sidebar-divider" aria-hidden="true" />
        <div className="media-sidebar-nav">
          {(rootCategories?.children || []).map((item) => {
            const active = topLevelPath === item.path;
            return (
              <Link
                key={item.path}
                className={`media-sidebar-link${active ? ' active' : ''}`}
                to={`/media?category_path=${encodeURIComponent(item.path)}`}
              >
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>
        {isAdmin ? (
          <Link to="/settings" className="media-settings-button" aria-label="打开设置页面">
            设置
          </Link>
        ) : null}
      </aside>
      <div className="media-main">
        <div className="panel media-browser-hero">
          <div className="media-subcategory-row">
            <button
              type="button"
              className="media-subcategory-refresh-button"
              onClick={handleRefreshSecondaryCategory}
              disabled={!currentSecondaryPath || refreshingCategory}
            >
              {refreshingCategory ? '刷新中...' : '刷新'}
            </button>
            {topLevelPath ? (
              <Link
                className={`media-subcategory-button${categoryPath === topLevelPath ? ' active' : ''}`}
                to={`/media?category_path=${encodeURIComponent(topLevelPath)}`}
              >
                全部
              </Link>
            ) : null}
            {secondaryItems.map((item) => {
              const active = categoryPath === item.path;
              return (
                <Link
                  key={item.path}
                  className={`media-subcategory-button${active ? ' active' : ''}`}
                  to={`/media?category_path=${encodeURIComponent(item.path)}`}
                >
                  {item.name}
                </Link>
              );
            })}
          </div>
          {refreshMessage ? <div className="muted-text media-subcategory-refresh-message">{refreshMessage}</div> : null}
          <div className="media-year-row">
            <button
              type="button"
              className={`media-year-button${!selectedYear ? ' active' : ''}`}
              onClick={() => setSelectedYear(null)}
            >
              全部年份
            </button>
            {years.map((itemYear) => (
              <button
                type="button"
                key={itemYear}
                className={`media-year-button${selectedYear === itemYear ? ' active' : ''}`}
                onClick={() => setSelectedYear(itemYear)}
              >
                {itemYear}
              </button>
            ))}
          </div>
        </div>
        <div className="panel media-browser-content">
          <AsyncState loading={loading && items.length === 0} error={error} empty={!loading && !error && !items.length} emptyText="没有匹配到媒体数据。">
            <>
              <div className="media-grid media-grid-emby">
                {visibleItems.map((item) => (
                  <MediaCard key={item.id} item={item} />
                ))}
              </div>
              {hasNext ? <div className="media-load-trigger" ref={loadMoreRef}>正在加载更多...</div> : null}
            </>
          </AsyncState>
        </div>
      </div>
    </section>
  );
}
