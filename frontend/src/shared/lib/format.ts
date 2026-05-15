export function formatRating(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value) || value <= 0) return '无评分';
  return `${value.toFixed(1)} / 10`;
}

export function formatMediaType(value: string | null | undefined) {
  if (value === 'tv') return '剧集';
  if (value === 'movie') return '电影';
  return '未知类型';
}

export function formatPlayedAt(value: string | null | undefined) {
  const timestamp = Number(value);
  if (!timestamp || Number.isNaN(timestamp)) return '时间未知';

  const date = new Date(timestamp * 1000);
  const now = new Date();
  const sameYear = date.getFullYear() === now.getFullYear();
  const pad = (input: number) => String(input).padStart(2, '0');

  if (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  ) {
    return `今天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate()
  ) {
    return `昨天 ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  const monthDay = `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  return sameYear ? monthDay : `${date.getFullYear()}-${monthDay}`;
}
