import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section className="panel">
      <p className="eyebrow">404</p>
      <h2 className="page-title">页面不存在</h2>
      <p className="muted-text">请返回分类页重新开始浏览。</p>
      <Link className="button" to="/categories">
        返回分类页
      </Link>
    </section>
  );
}