import { useState } from 'react';
import { refreshCategory } from '../../shared/api/media-api';
import { ApiClientError } from '../../shared/api/client';

interface RefreshButtonProps {
  categoryPath?: string;
  onRefreshed: () => void;
}

export function RefreshButton({ categoryPath, onRefreshed }: RefreshButtonProps) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleRefresh() {
    if (!categoryPath || pending) return;
    setPending(true);
    setMessage(null);
    try {
      const result = await refreshCategory(categoryPath);
      setMessage(`刷新完成：${result.item_count} 条媒体。`);
      onRefreshed();
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setMessage(reason.message);
      } else {
        setMessage('刷新失败，请稍后重试。');
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <button type="button" onClick={handleRefresh} disabled={!categoryPath || pending}>
        {pending ? '刷新中...' : '刷新当前分类'}
      </button>
      {message ? <p className="muted-text">{message}</p> : null}
    </div>
  );
}