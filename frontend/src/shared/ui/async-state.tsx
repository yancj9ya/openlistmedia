import type { ReactNode } from 'react';

interface AsyncStateProps {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyText?: string;
  children: ReactNode;
}

export function AsyncState({ loading, error, empty, emptyText, children }: AsyncStateProps) {
  if (loading) return <div className="state-card">加载中...</div>;
  if (error) return <div className="state-card state-card-error">{error}</div>;
  if (empty) return <div className="state-card">{emptyText || '暂无数据'}</div>;
  return <>{children}</>;
}