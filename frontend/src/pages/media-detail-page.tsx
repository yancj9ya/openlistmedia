import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { toDetailTitle } from '../entities/media/model';
import { useMediaDetail } from '../features/media-browser/use-media-detail';
import { ApiClientError } from '../shared/api/client';
import {
  createPlaylist,
  getDefaultPlayer,
  getLastPlayedEpisode,
  getPlayedEpisodes,
  getPlayLinkWithCategoryRefresh,
  getPlayerOptions,
  openWithPlayer,
  recordPlayedEpisodes,
  recordPlayHistory,
  refreshMediaItem,
  setDefaultPlayer,
  type PlayerType,
} from '../shared/api/media-api';
import type { MediaFileDto } from '../shared/api/types';
import { formatMediaType, formatRating } from '../shared/lib/format';
import { AsyncState } from '../shared/ui/async-state';

function formatEpisodeLabel(file: MediaFileDto, index: number) {
  const episodeNumber = file.episode_numbers?.[0] ?? extractEpisodeNumber(file.name || file.path);
  return String(episodeNumber ?? index + 1).padStart(2, '0');
}

function extractEpisodeNumber(value: string | null | undefined) {
  if (!value) return null;
  const name = value.split(/[\\/]/).pop() || value;
  const seasonEpisodeMatch = /S\d{1,2}E(\d{1,3})/i.exec(name);
  if (seasonEpisodeMatch) return Number(seasonEpisodeMatch[1]);

  return null;
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
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerType>(() => getDefaultPlayer());
  const [lastEpisodePath, setLastEpisodePath] = useState<string | null>(null);
  const [playedEpisodePaths, setPlayedEpisodePaths] = useState<string[]>([]);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [buildingPlaylist, setBuildingPlaylist] = useState(false);
  const playerOptions = useMemo(() => getPlayerOptions(), []);
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
  const playedEpisodePathSet = useMemo(() => new Set(playedEpisodePaths), [playedEpisodePaths]);
  const lastPlayedEpisodeIndex = useMemo(
    () => activeEpisodes.findIndex((file) => file.path === lastEpisodePath),
    [activeEpisodes, lastEpisodePath],
  );

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

  useEffect(() => {
    setDefaultPlayer(selectedPlayer);
  }, [selectedPlayer]);

  useEffect(() => {
    if (!playerOptions.some((option) => option.value === selectedPlayer)) {
      setSelectedPlayer(playerOptions[0]?.value || 'copy');
    }
  }, [playerOptions, selectedPlayer]);

  useEffect(() => {
    if (!mediaId) {
      setLastEpisodePath(null);
      return;
    }
    let cancelled = false;
    getLastPlayedEpisode(Number(mediaId))
      .then((result) => {
        if (!cancelled) setLastEpisodePath(result?.file_path ?? null);
      })
      .catch(() => {
        if (!cancelled) setLastEpisodePath(null);
      });
    return () => {
      cancelled = true;
    };
  }, [mediaId]);

  useEffect(() => {
    if (!mediaId) {
      setPlayedEpisodePaths([]);
      return;
    }
    let cancelled = false;
    getPlayedEpisodes(Number(mediaId))
      .then((result) => {
        if (!cancelled) setPlayedEpisodePaths(result.items.map((item) => item.file_path));
      })
      .catch(() => {
        if (!cancelled) setPlayedEpisodePaths([]);
      });
    return () => {
      cancelled = true;
    };
  }, [mediaId]);

  useEffect(() => {
    if (!selectionMode) {
      setSelectedPaths([]);
    }
  }, [selectionMode]);

  function togglePath(path: string) {
    setSelectedPaths((current) =>
      current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
    );
  }

  async function handleMergePlay() {
    if (selectedPaths.length === 0 || buildingPlaylist) return;
    try {
      setBuildingPlaylist(true);
      setActionMessage(null);
      const pathsToMark = [...selectedPaths];
      const result = await createPlaylist(pathsToMark);
      const m3uUrl = `${window.location.origin}/api/v1/playlist/${result.id}.m3u`;
      await openWithPlayer(selectedPlayer, m3uUrl);
      if (mediaId) {
        recordPlayedEpisodes(Number(mediaId), pathsToMark)
          .then((payload) => setPlayedEpisodePaths(payload.items.map((item) => item.file_path)))
          .catch(() => {
            setPlayedEpisodePaths((current) => Array.from(new Set([...current, ...pathsToMark])));
          });
        setPlayedEpisodePaths((current) => Array.from(new Set([...current, ...pathsToMark])));
      }
      setActionMessage(`已提交 ${result.count} 集播放列表给播放器。`);
      setSelectionMode(false);
      setSelectedPaths([]);
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setActionMessage(reason.message);
        return;
      }
      if (reason instanceof Error) {
        setActionMessage(reason.message);
        return;
      }
      setActionMessage('生成播放列表失败，请稍后重试。');
    } finally {
      setBuildingPlaylist(false);
    }
  }

  function handleSelectAfterLastPlayed() {
    if (!lastEpisodePath || !activeEpisodes.length) return;
    const index = activeEpisodes.findIndex((file) => file.path === lastEpisodePath);
    if (index < 0 || index >= activeEpisodes.length - 1) return;
    const nextPaths = activeEpisodes.slice(index + 1).map((file) => file.path);
    setSelectedPaths((current) => {
      const merged = new Set(current);
      nextPaths.forEach((p) => merged.add(p));
      return Array.from(merged);
    });
  }

  async function handlePlay(path: string) {
    try {
      setLoadingPath(path);
      setActionMessage(null);
      const payload = await getPlayLinkWithCategoryRefresh(path, mediaPath);
      if (!payload.playable_url) {
        setActionMessage('文件路径可能已变化，已尝试刷新缓存，但仍未找到可播放地址。');
        return;
      }
      if (mediaId) {
        recordPlayHistory(Number(mediaId), path);
        setLastEpisodePath(path);
        setPlayedEpisodePaths((current) => Array.from(new Set([...current, path])));
      }
      const message = await openWithPlayer(selectedPlayer, payload.playable_url);
      setActionMessage(message);
    } catch (reason) {
      if (reason instanceof ApiClientError) {
        setActionMessage(reason.message);
        return;
      }
      if (reason instanceof Error) {
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
                <div className="detail-files-header">
                    <strong>播放列表</strong>
                    <div className="detail-player-switcher" role="group" aria-label="选择播放器">
                    {playerOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={`detail-player-button${selectedPlayer === option.value ? ' active' : ''}`}
                        onClick={() => setSelectedPlayer(option.value)}
                      >
                        {option.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      className={`detail-player-button${selectionMode ? ' active' : ''}`}
                      onClick={() => setSelectionMode((current) => !current)}
                    >
                      {selectionMode ? '退出多选' : '多选'}
                    </button>
                  </div>
                </div>
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
                  {activeEpisodes.map((file, index) => {
                    const isPlayed = playedEpisodePathSet.has(file.path);
                    const isLastPlayed = lastPlayedEpisodeIndex === index;
                    const isSelected = selectionMode && selectedPaths.includes(file.path);
                    const isLoading = loadingPath === file.path && !selectionMode;
                    const className = [
                      'detail-episode-button',
                      isLoading ? 'loading' : '',
                      isPlayed ? 'played' : '',
                      isLastPlayed ? 'last-played' : '',
                      isSelected ? 'selected' : '',
                    ]
                      .filter(Boolean)
                      .join(' ');
                    return (
                      <button
                        key={`${file.path}-${file.name}`}
                        type="button"
                        className={className}
                        onClick={() => {
                          if (selectionMode) {
                            togglePath(file.path);
                          } else {
                            handlePlay(file.path);
                          }
                        }}
                        disabled={!selectionMode && (isLoading || refreshingDetail)}
                        title={file.name}
                      >
                        {isLoading ? '...' : formatEpisodeLabel(file, index)}
                      </button>
                    );
                  })}
                  {!activeEpisodes.length ? <div className="muted-text">暂无剧集。</div> : null}
                </div>
                {selectionMode ? (
                  <div className="detail-selection-bar">
                    <span className="detail-selection-bar-count">已选 {selectedPaths.length} 集</span>
                    <div className="detail-selection-bar-actions">
                      {(() => {
                        if (!lastEpisodePath) return null;
                        const idx = activeEpisodes.findIndex((file) => file.path === lastEpisodePath);
                        if (idx < 0 || idx >= activeEpisodes.length - 1) return null;
                        return (
                          <button
                            type="button"
                            className="button secondary"
                            onClick={handleSelectAfterLastPlayed}
                            disabled={buildingPlaylist}
                            title="从上次播放的集之后全部选中"
                          >
                            续选此后
                          </button>
                        );
                      })()}
                      <button
                        type="button"
                        className="button secondary"
                        onClick={() => setSelectedPaths([])}
                        disabled={selectedPaths.length === 0 || buildingPlaylist}
                      >
                        清除
                      </button>
                      <button
                        type="button"
                        onClick={handleMergePlay}
                        disabled={selectedPaths.length === 0 || buildingPlaylist}
                      >
                        {buildingPlaylist ? '生成中...' : '合并播放'}
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
