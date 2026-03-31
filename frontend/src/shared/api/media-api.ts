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

export function openMpv(url?: string | null) {
  if (!url) return;
  window.location.href = url;
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