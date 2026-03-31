import { buildApiUrl } from './config';
import type { ApiErrorResponse, ApiSuccessResponse } from './types';

export class ApiClientError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function toQueryString(params?: Record<string, string | number | undefined>) {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === '') return;
    searchParams.set(key, String(value));
  });
  const query = searchParams.toString();
  return query ? `?${query}` : '';
}

export async function requestJson<T>(
  path: string,
  options?: RequestInit,
  query?: Record<string, string | number | undefined>,
): Promise<T> {
  const response = await fetch(`${buildApiUrl(path)}${toQueryString(query)}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });

  const payload = (await response.json().catch(() => null)) as ApiSuccessResponse<T> | ApiErrorResponse | null;

  if (!response.ok || !payload?.success) {
    const error = payload && !payload.success ? payload.error : undefined;
    throw new ApiClientError(
      response.status,
      error?.code || 'http_error',
      error?.message || `Request failed with status ${response.status}`,
      error?.details,
    );
  }

  return payload.data;
}