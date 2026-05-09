import { adminToken } from './config';
import { ApiClientError, requestJson } from './client';
import type {
  AccessLoginResponseDto,
  AppSettingsDto,
  CategoryTreeDto,
  CreatePlaylistResponseDto,
  LastPlayedEpisodeDto,
  MediaDetailDto,
  PlayedEpisodesResponseDto,
  MediaListQuery,
  MediaListResponseDto,
  PlayHistoryDto,
  PlayLinkDto,
  RefreshResponseDto,
  SaveSettingsResponseDto,
} from './types';

const ACCESS_STORAGE_KEY = 'openlistmedia:auth';
export const PLAYER_PREFERENCE_STORAGE_KEY = 'openlistmedia:preferred-player';

export type PlayerType = 'mpv' | 'potplayer' | 'system' | 'nplayer' | 'infuse' | 'copy';

const DESKTOP_PLAYER_OPTIONS: Array<{ value: PlayerType; label: string }> = [
  { value: 'mpv', label: 'MPV' },
  { value: 'potplayer', label: 'PotPlayer' },
  { value: 'copy', label: '复制链接' },
];

const MOBILE_PLAYER_OPTIONS: Array<{ value: PlayerType; label: string }> = [
  { value: 'system', label: '系统播放' },
  { value: 'copy', label: '复制链接' },
];

const IOS_PLAYER_OPTIONS: Array<{ value: PlayerType; label: string }> = [
  { value: 'system', label: '系统播放' },
  { value: 'nplayer', label: 'nPlayer' },
  { value: 'infuse', label: 'Infuse' },
  { value: 'copy', label: '复制链接' },
];

function getAccessPasscode() {
  if (typeof window === 'undefined') {
    return '';
  }
  try {
    const raw = window.localStorage.getItem(ACCESS_STORAGE_KEY);
    if (!raw) {
      return '';
    }
    const parsed = JSON.parse(raw) as { passcode?: string };
    return String(parsed.passcode || '').trim();
  } catch {
    return '';
  }
}

export function getCategoryTree(path?: string, signal?: AbortSignal) {
  return requestJson<CategoryTreeDto>('/categories', { signal }, {
    path,
  });
}

export function getMediaList(query: MediaListQuery, signal?: AbortSignal) {
  return requestJson<MediaListResponseDto>('/media', { signal }, {
    category_path: query.categoryPath,
    include_descendants: query.includeDescendants ? 1 : undefined,
    year: query.year,
    keyword: query.keyword,
    type: query.type,
    page: query.page,
    page_size: query.pageSize,
    sort_by: query.sortBy,
    sort_order: query.sortOrder,
  });
}

export function getMediaDetail(mediaId: number, signal?: AbortSignal) {
  return requestJson<MediaDetailDto>(`/media/${mediaId}`, { signal });
}

export function isMobileDevice() {
  if (typeof window === 'undefined') {
    return false;
  }
  const userAgentData = (window.navigator as Navigator & { userAgentData?: { mobile?: boolean } }).userAgentData;
  if (typeof userAgentData?.mobile === 'boolean') {
    return userAgentData.mobile;
  }
  const userAgent = window.navigator.userAgent;
  return /iPhone|iPod|Android.+Mobile|Windows Phone|Mobile/i.test(userAgent);
}

export function isIosDevice() {
  if (typeof window === 'undefined') {
    return false;
  }
  const userAgent = window.navigator.userAgent;
  const platform = window.navigator.platform || '';
  const maxTouchPoints = window.navigator.maxTouchPoints || 0;
  return /iPhone|iPad|iPod/i.test(userAgent) || (platform === 'MacIntel' && maxTouchPoints > 1);
}

export function getPlayerOptions(): Array<{ value: PlayerType; label: string }> {
  if (isIosDevice()) {
    return IOS_PLAYER_OPTIONS;
  }
  return isMobileDevice() ? MOBILE_PLAYER_OPTIONS : DESKTOP_PLAYER_OPTIONS;
}

export function getDefaultPlayer(): PlayerType {
  const options = getPlayerOptions();
  const fallback = options[0]?.value || 'copy';
  if (typeof window === 'undefined') {
    return fallback;
  }
  const rawValue = window.localStorage.getItem(PLAYER_PREFERENCE_STORAGE_KEY);
  if (isPlayerType(rawValue) && options.some((item) => item.value === rawValue)) {
    return rawValue;
  }
  return fallback;
}

export function setDefaultPlayer(player: PlayerType) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(PLAYER_PREFERENCE_STORAGE_KEY, player);
}

export async function openWithPlayer(player: PlayerType, playableUrl?: string | null): Promise<string | null> {
  if (!playableUrl) {
    return null;
  }
  if (player === 'copy') {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(playableUrl);
      return '播放链接已复制到剪贴板。';
    }
    throw new Error('当前环境不支持自动复制链接。');
  }
  if (typeof window === 'undefined') {
    return null;
  }
  if (player === 'system') {
    window.location.href = playableUrl;
    return null;
  }
  if (player === 'nplayer') {
    window.location.href = `nplayer-${playableUrl}`;
    return null;
  }
  if (player === 'infuse') {
    window.location.href = `infuse://x-callback-url/play?url=${encodeURIComponent(playableUrl)}`;
    return null;
  }
  if (player === 'potplayer') {
    window.location.href = `potplayer://${playableUrl}`;
    return null;
  }
  window.location.href = `mpv://${playableUrl}`;
  return null;
}

function isPlayerType(value: string | null): value is PlayerType {
  return value === 'mpv' || value === 'potplayer' || value === 'system' || value === 'nplayer' || value === 'infuse' || value === 'copy';
}

export function getPlayLink(path: string) {
  return requestJson<PlayLinkDto>('/play-link', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function getPlayLinkWithCategoryRefresh(path: string, mediaPath?: string | null) {
  try {
    return await getPlayLink(path);
  } catch (error) {
    if (!mediaPath) {
      throw error;
    }
    await refreshMediaItem(mediaPath);
    return getPlayLink(path);
  }
}

export function refreshCategory(categoryPath: string) {
  return requestJson<RefreshResponseDto>('/refresh', {
    method: 'POST',
    headers: adminToken ? { 'X-Admin-Token': adminToken } : undefined,
    body: JSON.stringify({ category_path: categoryPath }),
  });
}

export function refreshMediaItem(mediaPath: string) {
  return requestJson<RefreshResponseDto>('/refresh', {
    method: 'POST',
    headers: adminToken ? { 'X-Admin-Token': adminToken } : undefined,
    body: JSON.stringify({ media_path: mediaPath }),
  });
}
export function getSettings() {
  const passcode = getAccessPasscode();
  return requestJson<AppSettingsDto>('/settings', {
    headers: passcode ? { 'X-Access-Passcode': passcode } : undefined,
  });
}

export function saveSettings(payload: AppSettingsDto) {
  const passcode = getAccessPasscode();
  return requestJson<SaveSettingsResponseDto>('/settings', {
    method: 'POST',
    headers: passcode ? { 'X-Access-Passcode': passcode } : undefined,
    body: JSON.stringify(payload),
  });
}

export function getRecentPlayHistory(signal?: AbortSignal) {
  return requestJson<PlayHistoryDto[]>('/recent-plays', { signal });
}

export async function recordPlayHistory(mediaId: number, filePath?: string | null): Promise<void> {
  try {
    await requestJson('/record-play', {
      method: 'POST',
      body: JSON.stringify({ media_id: mediaId, file_path: filePath || undefined }),
    });
  } catch {
    // 播放记录失败不影响用户体验，静默处理
  }
}

export async function getLastPlayedEpisode(
  mediaId: number,
  signal?: AbortSignal,
): Promise<LastPlayedEpisodeDto | null> {
  try {
    return await requestJson<LastPlayedEpisodeDto>(`/media/${mediaId}/last-episode`, { signal });
  } catch (reason) {
    if (reason instanceof ApiClientError && reason.status === 404) {
      return null;
    }
    throw reason;
  }
}

export async function getPlayedEpisodes(
  mediaId: number,
  signal?: AbortSignal,
): Promise<PlayedEpisodesResponseDto> {
  return requestJson<PlayedEpisodesResponseDto>(`/media/${mediaId}/played-episodes`, { signal });
}

export function recordPlayedEpisodes(mediaId: number, filePaths: string[]) {
  return requestJson<PlayedEpisodesResponseDto>(`/media/${mediaId}/played-episodes`, {
    method: 'POST',
    body: JSON.stringify({ file_paths: filePaths }),
  });
}

export function createPlaylist(paths: string[]) {
  return requestJson<CreatePlaylistResponseDto>('/playlist', {
    method: 'POST',
    body: JSON.stringify({ paths }),
  });
}

export function loginWithPasscode(passcode: string) {
  return requestJson<AccessLoginResponseDto>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ passcode }),
  });
}
