import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../app/providers';
import { ApiClientError } from '../shared/api/client';
import { loginWithPasscode } from '../shared/api/media-api';

export function AccessGatePage() {
  const { isAuthenticated, login } = useAuth();
  const [passcode, setPasscode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/media" replace />;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = passcode.trim();
    if (!value || submitting) {
      return;
    }
    try {
      setSubmitting(true);
      setError(null);
      const payload = await loginWithPasscode(value);
      login(payload.role, value);
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setError(reason.message);
      } else {
        setError('口令验证失败。');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="page-grid access-gate-layout">
      <div className="panel settings-panel access-gate-panel">
        <p className="eyebrow">openlist media</p>
        <h2 className="page-title">请输入访问口令</h2>
        <p className="muted-text settings-subtitle">支持管理者口令与访客口令。访客登录后将隐藏设置入口。</p>
        <form className="settings-form access-gate-form" onSubmit={handleSubmit}>
          <label className="access-gate-label">
            <span>访问口令</span>
            <input
              className="access-gate-input"
              type="password"
              value={passcode}
              onChange={(event) => setPasscode(event.target.value)}
              placeholder="请输入访问口令"
              autoFocus
            />
          </label>
          <div className="action-row settings-submit-row access-gate-submit-row">
            <button className="access-gate-submit-button" type="submit" disabled={submitting || !passcode.trim()}>
              {submitting ? '验证中...' : '进入媒体库'}
            </button>
          </div>
        </form>
        {error ? <div className="state-card state-card-error access-gate-error">{error}</div> : null}
      </div>
    </section>
  );
}
