import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { toDetailTitle } from '../entities/media/model';
import { useMediaDetail } from '../features/media-browser/use-media-detail';
import { ApiClientError } from '../shared/api/client';
import { getPlayLinkWithCategoryRefresh, openMpv, refreshMediaItem } from '../shared/api/media-api';
import type { MediaFileDto } from '../shared/api/types';
import { formatMediaType, formatRating } from '../shared/lib/format';
import { AsyncState } from '../shared/ui/async-state';

function formatEpisodeLabel(index: number) {
  return String(index + 1).padStart(2, '0');
}

export function MediaDetailPage() {
  const { mediaId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const backTo = (location.state as { from?: string } | null)?.from || '/media';
  const { data, loading, error, reload } = useMediaDetail(mediaId ? Number(mediaId) : null);
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [refreshingDetail, setRefreshingDetail] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const mediaPath = data?.openlist_path || null;
  const seasonOptions = useMemo(() => {
    if (!data) {
      return [];
    }
    if (data.seasons?.length) {
      return data.seasons
        .filter((season) => (season.episodes || []).length > 0)
        .map((season, index) => ({
          key: `season-${season.season_number}-${index}`,
          label: `S${season.season_number}`,
          episodes: season.episodes || [],
        }));
    }
    if (data.files?.length) {
      return [
        {
          key: 'season-default',
          label: '播放列表',
          episodes: data.files,
        },
      ];
    }
    return [];
  }, [data]);
  const [selectedSeasonKey, setSelectedSeasonKey] = useState<string>('');
  const activeSeason = seasonOptions.find((season) => season.key === selectedSeasonKey) || seasonOptions[0] || null;
  const activeEpisodes: MediaFileDto[] = activeSeason?.episodes || [];

  useEffect(() => {
    if (!seasonOptions.length) {
      setSelectedSeasonKey('');
      return;
    }
    setSelectedSeasonKey((current) => {
      if (current && seasonOptions.some((season) => season.key === current)) {
        return current;
      }
      return seasonOptions[0].key;
    });
  }, [seasonOptions]);

  async function handlePlay(path: string) {
    try {
      setLoadingPath(path);
      setActionMessage(null);
      const payload = await getPlayLinkWithCategoryRefresh(path, mediaPath);
      if (!payload.mpv_url) {
        setActionMessage('文件路径可能已变化，已尝试刷新缓存，但仍未找到可播放地址。');
        return;
      }
      openMpv(payload.mpv_url);
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setActionMessage(reason.message);
        return;
      }
      setActionMessage('播放地址获取失败，请稍后重试。');
    } finally {
      setLoadingPath(null);
    }
  }

  async function handleForceRefresh() {
    if (!mediaPath || refreshingDetail) {
      return;
    }
    try {
      setRefreshingDetail(true);
      setActionMessage(null);
      const refreshed = await refreshMediaItem(mediaPath);
      if (refreshed.media_id && String(refreshed.media_id) !== String(mediaId || '')) {
        navigate(`/media/${refreshed.media_id}`, {
          replace: true,
          state: { from: backTo },
        });
        setActionMessage('当前详情已刷新，并已跳转到最新媒体记录。');
        return;
      }
      reload();
      setActionMessage(
        refreshed.openlist_refreshed
          ? '当前详情对应媒体目录已强制刷新，并已同步 OpenList 目录。'
          : '当前详情对应媒体目录已强制刷新。',
      );
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setActionMessage(reason.message);
        return;
      }
      setActionMessage('目录刷新失败，请稍后重试。');
    } finally {
      setRefreshingDetail(false);
    }
  }

  const backdropStyle = data?.backdrop_url
    ? {
        backgroundImage: `linear-gradient(180deg, rgba(9,12,20,0.36) 0%, rgba(9,12,20,0.82) 55%, rgba(9,12,20,0.98) 100%), url(${data.backdrop_url})`,
      }
    : undefined;

  return (
    <section className="page-grid detail-page">
      <AsyncState loading={loading} error={error} empty={!loading && !error && !data} emptyText="未找到媒体详情。">
        {data ? (
          <div className="detail-hero detail-hero-fullscreen" style={backdropStyle}>
            <div className="action-row detail-topbar">
              <Link className="detail-back-button" to={backTo} aria-label="返回列表">
                <svg className="detail-back-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M14.5 6.5L9 12l5.5 5.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </Link>
              <button
                type="button"
                className="detail-refresh-button"
                onClick={handleForceRefresh}
                disabled={!mediaPath || refreshingDetail}
              >
                {refreshingDetail ? '刷新中...' : '刷新'}
              </button>
            </div>
            <div className="detail-hero-content">
              <div className="detail-copy">
                <p className="eyebrow">{formatMediaType(data.type)} / TMDb {data.tmdb_id || '-'}</p>
                <h2 className="page-title detail-title">{toDetailTitle(data)}</h2>
                <div className="chip-row detail-summary-chips">
                  <span className="chip">年份 {data.year || '-'}</span>
                  <span className="chip">评分 {formatRating(data.vote_average)}</span>
                  <span className="chip">分类 {data.category_label || '未分类'}</span>
                  {(data.genres || []).slice(0, 4).map((genre) => (
                    <span className="chip" key={genre}>{genre}</span>
                  ))}
                </div>
                <p className="muted-text detail-overview">{data.overview || '暂无简介'}</p>
                {actionMessage ? <p className="muted-text detail-action-message">{actionMessage}</p> : null}
              </div>
              <div className="file-item detail-files-card detail-files-scroll">
                <strong>播放列表</strong>
                {seasonOptions.length > 1 ? (
                  <>
                    <div className="detail-season-tabs" role="tablist" aria-label="选择季">
                      {seasonOptions.map((season) => (
                        <button
                          key={season.key}
                          type="button"
                          className={`detail-season-tab${selectedSeasonKey === season.key ? ' active' : ''}`}
                          onClick={() => setSelectedSeasonKey(season.key)}
                        >
                          {season.label}
                        </button>
                      ))}
                    </div>
                    <div className="detail-season-divider" aria-hidden="true" />
                  </>
                ) : null}
                <div className="detail-episode-grid">
                  {activeEpisodes.map((file, index) => (
                    <button
                      key={`${file.path}-${file.name}`}
                      type="button"
                      className={`detail-episode-button${loadingPath === file.path ? ' loading' : ''}`}
                      onClick={() => handlePlay(file.path)}
                      disabled={loadingPath === file.path || refreshingDetail}
                      title={file.name}
                    >
                      {loadingPath === file.path ? '...' : formatEpisodeLabel(index)}
                    </button>
                  ))}
                  {!activeEpisodes.length ? <div className="muted-text">暂无剧集。</div> : null}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}