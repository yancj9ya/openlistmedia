import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../app/providers';
import { getSettings, saveSettings } from '../shared/api/media-api';
import type { AppSettingsDto } from '../shared/api/types';
import { ApiClientError } from '../shared/api/client';

type SettingsTabKey = 'openlist' | 'tmdb' | 'media-wall' | 'app';

const SETTINGS_TABS: Array<{ key: SettingsTabKey; label: string; description: string }> = [
  { key: 'openlist', label: 'OpenList', description: '资源站连接与认证' },
  { key: 'tmdb', label: 'TMDb', description: '元数据与封面来源' },
  { key: 'media-wall', label: '媒体墙', description: '目录、缓存与播放模板' },
  { key: 'app', label: '前后端', description: '监听地址、站点与访问口令' },
];

export function SettingsPage() {
  const { isAdmin } = useAuth();
  const [settings, setSettings] = useState<AppSettingsDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [skipDirectoriesInput, setSkipDirectoriesInput] = useState('');
  const [activeTab, setActiveTab] = useState<SettingsTabKey>('openlist');

  useEffect(() => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getSettings()
      .then((payload) => {
        if (!cancelled) {
          setSettings(payload);
          setSkipDirectoriesInput((payload.media_wall.skip_directories || []).join(' | '));
        }
      })
      .catch((reason) => {
        if (cancelled) return;
        if (reason instanceof ApiClientError) {
          setError(reason.message);
          return;
        }
        setError('设置加载失败。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  function updateField(path: string[], value: string | boolean | string[]) {
    setSettings((current) => {
      if (!current) return current;
      const next = structuredClone(current) as AppSettingsDto;
      let cursor: Record<string, unknown> = next as unknown as Record<string, unknown>;
      for (let index = 0; index < path.length - 1; index += 1) {
        cursor = cursor[path[index]] as Record<string, unknown>;
      }
      cursor[path[path.length - 1]] = value;
      return next;
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = await saveSettings(settings);
      setSettings(payload);
      setSkipDirectoriesInput((payload.media_wall.skip_directories || []).join(' | '));
      setMessage('配置已保存到 config.yml');
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setError(reason.message);
      } else {
        setError('配置保存失败。');
      }
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) {
    return (
      <section className="page-grid settings-page-shell">
        <div className="panel settings-panel">
          <div className="state-card state-card-error">仅管理者可以访问设置页面。</div>
        </div>
      </section>
    );
  }

  return (
    <section className="page-grid settings-page-shell">
      <div className="panel settings-panel settings-panel-wide">
        <div className="action-row settings-header-row">
          <div>
            <p className="eyebrow">设置</p>
            <h2 className="page-title">配置中心</h2>
            <p className="muted-text settings-subtitle">这里可以直接编辑站点连接、媒体墙参数以及 MPV 播放入口域名。</p>
          </div>
          <Link className="button secondary" to="/media">
            返回媒体页
          </Link>
        </div>
        {loading ? <div className="state-card">加载设置中...</div> : null}
        {error ? <div className="state-card state-card-error">{error}</div> : null}
        {message ? <div className="state-card">{message}</div> : null}
        {settings ? (
          <form className="settings-form" onSubmit={handleSubmit}>
            <div className="settings-overview-grid">
              <div className="settings-overview-card">
                <span className="settings-overview-label">OpenList</span>
                <strong>{settings.openlist.base_url || '未配置'}</strong>
              </div>
              <div className="settings-overview-card">
                <span className="settings-overview-label">媒体根目录</span>
                <strong>{settings.media_wall.media_root || '未配置'}</strong>
              </div>
              <div className="settings-overview-card">
                <span className="settings-overview-label">API</span>
                <strong>{`${settings.backend.host}:${settings.backend.port}${settings.backend.api_prefix}`}</strong>
              </div>
            </div>
            <div className="settings-tabs" role="tablist" aria-label="配置模块切换">
              {SETTINGS_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.key}
                  className={`settings-tab${activeTab === tab.key ? ' active' : ''}`}
                  onClick={() => setActiveTab(tab.key)}
                >
                  <span>{tab.label}</span>
                  <small>{tab.description}</small>
                </button>
              ))}
            </div>
            <div className="settings-grid settings-grid-compact settings-grid-single">
              {activeTab === 'openlist' ? (
                <section className="file-item settings-section settings-section-full">
                <div className="settings-section-heading">
                  <div>
                    <h3>OpenList</h3>
                    <p className="muted-text">配置资源站连接与认证信息。</p>
                  </div>
                </div>
                <div className="settings-fields-grid">
                  <label>
                    <span>Base URL</span>
                    <input value={settings.openlist.base_url} onChange={(event) => updateField(['openlist', 'base_url'], event.target.value)} />
                  </label>
                  <label>
                    <span>Token</span>
                    <input value={settings.openlist.token} onChange={(event) => updateField(['openlist', 'token'], event.target.value)} />
                  </label>
                  <label>
                    <span>Username</span>
                    <input value={settings.openlist.username} onChange={(event) => updateField(['openlist', 'username'], event.target.value)} />
                  </label>
                  <label>
                    <span>Password</span>
                    <input type="password" value={settings.openlist.password} onChange={(event) => updateField(['openlist', 'password'], event.target.value)} />
                  </label>
                </div>
                </section>
              ) : null}
              {activeTab === 'tmdb' ? (
                <section className="file-item settings-section settings-section-full">
                <div className="settings-section-heading">
                  <div>
                    <h3>TMDb</h3>
                    <p className="muted-text">补充元数据、语言与封面来源。</p>
                  </div>
                </div>
                <label>
                  <span>Read Access Token</span>
                  <input value={settings.tmdb.read_access_token} onChange={(event) => updateField(['tmdb', 'read_access_token'], event.target.value)} />
                </label>
                <label>
                  <span>API Key</span>
                  <input value={settings.tmdb.api_key} onChange={(event) => updateField(['tmdb', 'api_key'], event.target.value)} />
                </label>
                <label>
                  <span>Language</span>
                  <input value={settings.tmdb.language} onChange={(event) => updateField(['tmdb', 'language'], event.target.value)} />
                </label>
                </section>
              ) : null}
              {activeTab === 'media-wall' ? (
                <section className="file-item settings-section settings-section-full">
                <div className="settings-section-heading">
                  <div>
                    <h3>媒体墙</h3>
                    <p className="muted-text">控制目录、缓存与公网播放模板。</p>
                  </div>
                </div>
                <label>
                  <span>媒体根目录</span>
                  <input value={settings.media_wall.media_root} onChange={(event) => updateField(['media_wall', 'media_root'], event.target.value)} />
                </label>
                <label>
                  <span>站点目录</span>
                  <input value={settings.media_wall.site_dir} onChange={(event) => updateField(['media_wall', 'site_dir'], event.target.value)} />
                </label>
                <label>
                  <span>数据库路径</span>
                  <input value={settings.media_wall.database_path} onChange={(event) => updateField(['media_wall', 'database_path'], event.target.value)} />
                </label>
                <label>
                  <span>公网播放 URL 模板</span>
                  <input value={settings.media_wall.item_url_template} onChange={(event) => updateField(['media_wall', 'item_url_template'], event.target.value)} />
                </label>
                <label>
                  <span>跳过目录（使用 | 分隔）</span>
                  <input
                    value={skipDirectoriesInput}
                    onChange={(event) => {
                      const rawValue = event.target.value;
                      setSkipDirectoriesInput(rawValue);
                      updateField(
                        ['media_wall', 'skip_directories'],
                        rawValue.split('|').map((item) => item.trim()).filter(Boolean),
                      );
                    }}
                  />
                </label>
                </section>
              ) : null}
              {activeTab === 'app' ? (
                <section className="file-item settings-section settings-section-full">
                <div className="settings-section-heading">
                  <div>
                    <h3>前后端</h3>
                    <p className="muted-text">后端监听、前端站点地址与访问口令。</p>
                  </div>
                </div>
                <label>
                  <span>Backend Host</span>
                  <input value={settings.backend.host} onChange={(event) => updateField(['backend', 'host'], event.target.value)} />
                </label>
                <label>
                  <span>Backend Port</span>
                  <input value={String(settings.backend.port)} onChange={(event) => updateField(['backend', 'port'], String(Number(event.target.value) || 0))} />
                </label>
                <label>
                  <span>Frontend Site URL</span>
                  <input value={settings.frontend.site_url} onChange={(event) => updateField(['frontend', 'site_url'], event.target.value)} />
                </label>
                <label>
                  <span>API Prefix</span>
                  <input value={settings.backend.api_prefix} onChange={(event) => updateField(['backend', 'api_prefix'], event.target.value)} />
                </label>
                <label>
                  <span>管理者口令</span>
                  <input value={settings.frontend.admin_passcode} onChange={(event) => updateField(['frontend', 'admin_passcode'], event.target.value)} />
                </label>
                <label>
                  <span>访客口令</span>
                  <input value={settings.frontend.visitor_passcode} onChange={(event) => updateField(['frontend', 'visitor_passcode'], event.target.value)} />
                </label>
                </section>
              ) : null}
            </div>
            <div className="action-row settings-submit-row">
              <button type="submit" disabled={saving}>
                {saving ? '保存中...' : '保存配置'}
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </section>
  );
}
