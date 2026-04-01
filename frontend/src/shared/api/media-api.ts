import { adminToken } from './config';
import { requestJson } from './client';
import type {
  AccessLoginResponseDto,
  AppSettingsDto,
  CategoryTreeDto,
  MediaDetailDto,
  MediaListQuery,
  MediaListResponseDto,
  PlayLinkDto,
  RefreshResponseDto,
} from './types';

const ACCESS_STORAGE_KEY = 'openlistmedia:auth';
export const PLAYER_PREFERENCE_STORAGE_KEY = 'openlistmedia:preferred-player';

export type PlayerType = 'mpv' | 'potplayer' | 'copy';

export const PLAYER_OPTIONS: Array<{ value: PlayerType; label: string }> = [
  { value: 'mpv', label: 'MPV' },
  { value: 'potplayer', label: 'PotPlayer' },
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

export function getCategoryTree(path?: string) {
  return requestJson<CategoryTreeDto>('/categories', undefined, {
    path,
  });
}

export function getMediaList(query: MediaListQuery) {
  return requestJson<MediaListResponseDto>('/media', undefined, {
    category_path: query.categoryPath,
    include_descendants: query.includeDescendants ? 1 : undefined,
    year: query.year,
    keyword: query.keyword,
    type: query.type,
    page: query.page,
    page_size: query.pageSize,
  });
}

export function getMediaDetail(mediaId: number) {
  return requestJson<MediaDetailDto>(`/media/${mediaId}`);
}

export function getDefaultPlayer(): PlayerType {
  if (typeof window === 'undefined') {
    return 'mpv';
  }
  const rawValue = window.localStorage.getItem(PLAYER_PREFERENCE_STORAGE_KEY);
  return isPlayerType(rawValue) ? rawValue : 'mpv';
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
  if (player === 'potplayer') {
    window.location.href = `potplayer://${playableUrl}`;
    return null;
  }
  window.location.href = `mpv://${playableUrl}`;
  return null;
}

function isPlayerType(value: string | null): value is PlayerType {
  return value === 'mpv' || value === 'potplayer' || value === 'copy';
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
  return requestJson<AppSettingsDto>('/settings', {
    method: 'POST',
    headers: passcode ? { 'X-Access-Passcode': passcode } : undefined,
    body: JSON.stringify(payload),
  });
}

export function loginWithPasscode(passcode: string) {
  return requestJson<AccessLoginResponseDto>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ passcode }),
  });
}
