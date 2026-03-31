import { Link } from 'react-router-dom';
import type { CategoryTreeNode } from '../../shared/api/types';

interface CategoryCardProps {
  category: CategoryTreeNode;
}

export function CategoryCard({ category }: CategoryCardProps) {
  return (
    <article className="category-card">
      <div className="meta-row">
        <strong>{category.name}</strong>
        <span className="chip">{category.path}</span>
      </div>
      <p className="muted-text">子分类 {category.category_count_hint || 0} · 媒体 {category.media_count_hint || 0}</p>
      <div className="action-row">
        <Link className="button" to={`/media?category_path=${encodeURIComponent(category.path)}`}>
          浏览媒体
        </Link>
        <Link className="button secondary" to={`/categories?path=${encodeURIComponent(category.path)}`}>
          进入子分类
        </Link>
      </div>
    </article>
  );
}