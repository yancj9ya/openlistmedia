export function formatRating(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '暂无评分';
  return `${value.toFixed(1)} / 10`;
}

export function formatMediaType(value: string | null | undefined) {
  if (value === 'tv') return '剧集';
  if (value === 'movie') return '电影';
  return '未知类型';
}