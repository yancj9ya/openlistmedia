const rawApiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').trim();
const rawSiteBaseUrl = (import.meta.env.VITE_SITE_BASE_URL || '').trim();

export const apiBaseUrl = rawApiBaseUrl || '/api/v1';
export const siteBaseUrl = rawSiteBaseUrl || '/';
export const adminToken = (import.meta.env.VITE_ADMIN_TOKEN || '').trim();

export function buildApiUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (apiBaseUrl.startsWith('http://') || apiBaseUrl.startsWith('https://')) {
    return `${apiBaseUrl}${normalizedPath}`;
  }
  return `${apiBaseUrl.replace(/\/$/, '')}${normalizedPath}`;
}