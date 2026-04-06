import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CategoryCard } from '../entities/category/category-card';
import { MediaCard } from '../entities/media/media-card';
import { useCategoryTree } from '../features/media-browser/use-category-tree';
import { useRecentPlays } from '../features/media-browser/use-recent-plays';
import { AsyncState } from '../shared/ui/async-state';
import type { MediaListItemDto } from '../shared/api/types';

export function CategoriesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showRecentPlays, setShowRecentPlays] = useState(false);
  const path = searchParams.get('path');
  const { data, loading, error } = useCategoryTree(path);
  const { data: recentPlays, loading: recentLoading, error: recentError } = useRecentPlays();

  function goParent() {
    if (!data?.parentPath) return;
    setSearchParams({ path: data.parentPath });
  }

  const recentPlaysAsMediaItems: MediaListItemDto[] = (recentPlays || []).map((item) => ({
    id: item.media_id,
    title: item.media_title,
    type: item.media_type,
    poster_url: item.poster_url,
    display_title: null,
    original_title: null,
    year: null,
    overview: null,
    vote_average: null,
    backdrop_url: null,
    release_date: null,
    category_label: null,
    category_path: null,
    openlist_path: null,
    openlist_url: null,
    updated_at: null,
    tmdb_id: null,
  }));

  return (
    <section className="page-grid two-columns">
      <aside className="panel">
        <p className="eyebrow">分类浏览</p>
        <h2 className="page-title">目录导航</h2>
        <p className="muted-text">已落地根分类/子分类浏览、进入列表、返回上级。分类树只加载当前节点，更多树形缓存与批量展开能力暂预留。</p>
        <div className="breadcrumb-row">
          <span className="chip">当前路径：{data?.path || path || '根目录'}</span>
          {data?.parentPath ? (
            <button type="button" className="secondary" onClick={goParent}>
              返回上级
            </button>
          ) : null}
        </div>
        <div className="chip-row">
          {(data?.skipDirectories || []).map((item: string) => (
            <span className="chip" key={item}>
              已忽略：{item}
            </span>
          ))}
        </div>
        <button
          type="button"
          className={showRecentPlays ? 'primary' : 'secondary'}
          onClick={() => setShowRecentPlays(!showRecentPlays)}
          style={{ marginTop: '1rem', width: '100%' }}
        >
          {showRecentPlays ? '隐藏最近播放' : '显示最近播放'}
        </button>
      </aside>
      <div className="panel">
        {showRecentPlays ? (
          <AsyncState loading={recentLoading} error={recentError?.message} empty={!recentLoading && !recentError && !recentPlays?.length} emptyText="暂无播放记录。">
            <div className="category-list">
              {recentPlaysAsMediaItems.map((item) => (
                <MediaCard key={`${item.id}-recent`} item={item} />
              ))}
            </div>
          </AsyncState>
        ) : (
          <AsyncState loading={loading} error={error} empty={!loading && !error && !data?.children.length} emptyText="当前分类下暂无子目录。">
            <div className="category-list">
              {(data?.children || []).map((category) => (
                <CategoryCard key={category.path} category={category} />
              ))}
            </div>
          </AsyncState>
        )}
      </div>
    </section>
  );
}
