import { useSearchParams } from 'react-router-dom';
import { CategoryCard } from '../entities/category/category-card';
import { useCategoryTree } from '../features/media-browser/use-category-tree';
import { AsyncState } from '../shared/ui/async-state';

export function CategoriesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const path = searchParams.get('path');
  const { data, loading, error } = useCategoryTree(path);

  function goParent() {
    if (!data?.parentPath) return;
    setSearchParams({ path: data.parentPath });
  }

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
      </aside>
      <div className="panel">
        <AsyncState loading={loading} error={error} empty={!loading && !error && !data?.children.length} emptyText="当前分类下暂无子目录。">
          <div className="category-list">
            {(data?.children || []).map((category) => (
              <CategoryCard key={category.path} category={category} />
            ))}
          </div>
        </AsyncState>
      </div>
    </section>
  );
}