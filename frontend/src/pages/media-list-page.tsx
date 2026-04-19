import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../app/providers';
import { MediaCard } from '../entities/media/media-card';
import { useCategoryTree } from '../features/media-browser/use-category-tree';
import { useMediaList } from '../features/media-browser/use-media-list';
import { useRecentPlays } from '../features/media-browser/use-recent-plays';
import { ApiClientError } from '../shared/api/client';
import { refreshCategory } from '../shared/api/media-api';
import type { MediaListItemDto } from '../shared/api/types';
import { AsyncState } from '../shared/ui/async-state';

const DEFAULT_PAGE_SIZE = 20;

export function MediaListPage() {
  const { isAdmin, theme, setTheme } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const categoryPath = searchParams.get('category_path') || undefined;
  const keyword = searchParams.get('keyword') || undefined;
  const type = searchParams.get('type') || undefined;
  const yearParam = searchParams.get('year');
  const selectedYear = yearParam ? Number(yearParam) || null : null;
  const [showRecentPlays, setShowRecentPlays] = useState(() => !categoryPath && !keyword && !type);
  const [showMobileCategories, setShowMobileCategories] = useState(false);
  const [showMobileSubcategories, setShowMobileSubcategories] = useState(false);
  const [showMobileYears, setShowMobileYears] = useState(false);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<MediaListItemDto[]>([]);
  const [keywordInput, setKeywordInput] = useState(keyword || '');
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const pageSize = DEFAULT_PAGE_SIZE;
  const query = useMemo(
    () => ({
      categoryPath,
      includeDescendants: Boolean(categoryPath),
      keyword,
      type,
      year: selectedYear ?? undefined,
      page,
      pageSize,
    }),
    [categoryPath, keyword, page, pageSize, selectedYear, type],
  );
  const { data, loading, error, reload: reloadMediaList } = useMediaList(query);
  const { data: recentPlays, loading: recentLoading, error: recentError } = useRecentPlays();
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
  const years = useMemo(() => [...(data?.years || [])].sort((left, right) => right - left), [data?.years]);
  const hasNext = Boolean(data?.pagination.has_next);
  const currentSecondaryPath = categoryPath && categoryPath !== topLevelPath ? categoryPath : null;

  function updateSelectedYear(nextYear: number | null) {
    const nextParams = new URLSearchParams(searchParams);
    if (nextYear) {
      nextParams.set('year', String(nextYear));
    } else {
      nextParams.delete('year');
    }
    setSearchParams(nextParams);
  }

  useEffect(() => {
    setPage(1);
    setItems([]);
  }, [categoryPath, keyword, type, selectedYear]);
  const recentPlayItems = useMemo<MediaListItemDto[]>(
    () =>
      (recentPlays || []).map((item) => ({
        id: item.media_id,
        title: item.media_title,
        type: item.media_type,
        poster_url: item.poster_url,
        display_title: null,
        original_title: null,
        year: null,
        overview: null,
        backdrop_url: null,
        release_date: null,
        category_label: '最近播放',
        category_path: null,
        openlist_path: null,
        openlist_url: null,
        updated_at: String(item.played_at),
        vote_average: item.vote_average ?? null,
        tmdb_id: null,
      })),
    [recentPlays],
  );

  useEffect(() => {
    if (categoryPath || keyword || type) {
      setShowRecentPlays(false);
    }
  }, [categoryPath, keyword, type]);

  useEffect(() => {
    if (categoryPath || keyword || type || showRecentPlays) {
      setShowMobileCategories(false);
    }
  }, [categoryPath, keyword, type, showRecentPlays]);

  useEffect(() => {
    if (categoryPath || keyword || type || showRecentPlays) {
      setShowMobileSubcategories(false);
      setShowMobileYears(false);
    }
  }, [categoryPath, keyword, type, showRecentPlays]);

  useEffect(() => {
    setKeywordInput(keyword || '');
  }, [keyword]);

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

  function handleKeywordSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextParams = new URLSearchParams(searchParams);
    const trimmed = keywordInput.trim();
    if (trimmed) {
      nextParams.set('keyword', trimmed);
    } else {
      nextParams.delete('keyword');
    }
    setSearchParams(nextParams);
  }

  return (
    <section className="media-shell">
      <aside className="media-sidebar panel">
        <Link to="/media" className="media-sidebar-title">
          影视海报墙
        </Link>
        <p className="media-sidebar-subtitle">openlist</p>
        <div className="media-sidebar-divider" aria-hidden="true" />
        <button
          type="button"
          className="media-mobile-categories-toggle"
          onClick={() => setShowMobileCategories((current) => !current)}
          aria-expanded={showMobileCategories}
        >
          {showMobileCategories ? '收起分类' : '展开分类'}
        </button>
        <div className={`media-sidebar-nav${showMobileCategories ? ' mobile-open' : ''}`}>
          <button
            type="button"
            className={`media-sidebar-link${showRecentPlays ? ' active' : ''}`}
            onClick={() => {
              setShowRecentPlays((current) => !current);
              setShowMobileCategories(false);
            }}
          >
            <span>最近播放</span>
          </button>
          {(rootCategories?.children || []).map((item) => {
            const active = topLevelPath === item.path;
            return (
              <Link
                key={item.path}
                className={`media-sidebar-link${active && !showRecentPlays ? ' active' : ''}`}
                to={`/media?category_path=${encodeURIComponent(item.path)}`}
                onClick={() => setShowRecentPlays(false)}
              >
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>
        <div className="media-sidebar-footer">
          {isAdmin ? (
            <Link to="/settings" className="media-settings-button" aria-label="打开设置页面">
              设置
            </Link>
          ) : null}
          <button
            type="button"
            className="media-theme-toggle"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label="切换明暗主题"
          >
            {theme === 'dark' ? (
              <svg viewBox="0 0 24 24" aria-hidden="true" className="media-theme-icon">
                <path
                  d="M12 4.75a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V5.5a.75.75 0 0 1 .75-.75Zm0 11a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5Zm0 3.5a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V20a.75.75 0 0 1 .75-.75ZM6.343 6.343a.75.75 0 0 1 1.06 0l1.06 1.06a.75.75 0 1 1-1.06 1.06l-1.06-1.06a.75.75 0 0 1 0-1.06Zm9.194 9.194a.75.75 0 0 1 1.06 0l1.06 1.06a.75.75 0 1 1-1.06 1.06l-1.06-1.06a.75.75 0 0 1 0-1.06ZM4.75 12a.75.75 0 0 1 .75-.75H7a.75.75 0 0 1 0 1.5H5.5a.75.75 0 0 1-.75-.75Zm11.5 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5H17a.75.75 0 0 1-.75-.75ZM7.403 15.537a.75.75 0 0 1 1.06 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06Zm10.254-9.194a.75.75 0 0 1 0 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0Z"
                  fill="currentColor"
                />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true" className="media-theme-icon">
                <path
                  d="M14.53 2.47a.75.75 0 0 1 .82.2 8.75 8.75 0 1 0 5.98 11.98.75.75 0 0 1 1.02.9A10.25 10.25 0 1 1 13.45 1.45a.75.75 0 0 1 1.08 1.02 7.25 7.25 0 0 0 0 10.26 7.25 7.25 0 0 0 10.26 0 .75.75 0 0 1 1.02 1.08A8.74 8.74 0 0 1 14.53 2.47Z"
                  fill="currentColor"
                />
              </svg>
            )}
          </button>
        </div>
      </aside>
      <div className="media-main">
        {showRecentPlays ? (
          <div className="panel media-browser-hero">
            <p className="eyebrow">播放历史</p>
            <h2 className="page-title">最近播放</h2>
            <p className="muted-text">这里展示最近打开过的媒体，方便你快速回到上次观看的位置。</p>
          </div>
        ) : (
          <div className="panel media-browser-hero">
            <div className="media-subcategory-row media-subcategory-toolbar">
              <button
                type="button"
                className="media-mobile-filter-toggle"
                onClick={() => setShowMobileSubcategories((current) => !current)}
                aria-expanded={showMobileSubcategories}
              >
                {showMobileSubcategories ? '收起二级分类' : '展开二级分类'}
              </button>
              <div className={`media-subcategory-actions${showMobileSubcategories ? ' mobile-open' : ''}`}>
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
                    onClick={() => setShowMobileSubcategories(false)}
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
                      onClick={() => setShowMobileSubcategories(false)}
                    >
                      {item.name}
                    </Link>
                  );
                })}
              </div>
              <form className="media-subcategory-search" onSubmit={handleKeywordSubmit}>
                <input
                  type="search"
                  value={keywordInput}
                  onChange={(event) => setKeywordInput(event.target.value)}
                  placeholder="搜索当前分类中的剧名"
                  aria-label="搜索当前分类中的剧名"
                />
              </form>
            </div>
            {refreshMessage ? <div className="muted-text media-subcategory-refresh-message">{refreshMessage}</div> : null}
            <button
              type="button"
              className="media-mobile-filter-toggle"
              onClick={() => setShowMobileYears((current) => !current)}
              aria-expanded={showMobileYears}
            >
              {showMobileYears ? '收起年份' : '展开年份'}
            </button>
            <div className={`media-year-row${showMobileYears ? ' mobile-open' : ''}`}>
              <button
                type="button"
                className={`media-year-button${!selectedYear ? ' active' : ''}`}
                onClick={() => {
                  updateSelectedYear(null);
                  setShowMobileYears(false);
                }}
              >
                全部年份
              </button>
              {years.map((itemYear) => (
                <button
                  type="button"
                  key={itemYear}
                  className={`media-year-button${selectedYear === itemYear ? ' active' : ''}`}
                  onClick={() => {
                    updateSelectedYear(itemYear);
                    setShowMobileYears(false);
                  }}
                >
                  {itemYear}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="panel media-browser-content">
          {showRecentPlays ? (
            <AsyncState
              loading={recentLoading}
              error={recentError?.message}
              empty={!recentLoading && !recentError && !recentPlayItems.length}
              emptyText="暂无播放记录。"
            >
              <div className="media-grid media-grid-emby">
                {recentPlayItems.map((item) => (
                  <MediaCard key={`${item.id}-recent`} item={item} />
                ))}
              </div>
            </AsyncState>
          ) : (
            <AsyncState loading={loading && items.length === 0} error={error} empty={!loading && !error && !items.length} emptyText="没有匹配到媒体数据。">
              <>
                <div className="media-grid media-grid-emby">
                  {items.map((item) => (
                    <MediaCard key={item.id} item={item} />
                  ))}
                </div>
                {hasNext ? <div className="media-load-trigger" ref={loadMoreRef}>正在加载更多...</div> : null}
              </>
            </AsyncState>
          )}
        </div>
      </div>
    </section>
  );
}
