import type { MediaDetailDto, MediaListItemDto } from '../../shared/api/types';
import { formatMediaType, formatPlayedAt, formatRating } from '../../shared/lib/format';

export interface MediaCardModel {
  id: number;
  title: string;
  subtitle: string;
  overview: string;
  posterUrl: string | null;
  metaTags: string[];
}

export function toMediaCardModel(item: MediaListItemDto): MediaCardModel {
  const isRecentPlayCard = item.category_label === '最近播放';
  const typeLabel = formatMediaType(item.type);
  const ratingLabel = formatRating(item.vote_average);
  const playedAtLabel = formatPlayedAt(item.updated_at);

  return {
    id: item.id,
    title: item.display_title || item.title,
    subtitle: item.original_title || '',
    overview: item.overview || '暂无简介',
    posterUrl: item.poster_url,
    metaTags: isRecentPlayCard
      ? [typeLabel, playedAtLabel, ratingLabel]
      : [item.category_label || '未分类', item.year ? String(item.year) : '-', ratingLabel],
  };
}

export function createMediaStats(items: MediaListItemDto[]) {
  const movieCount = items.filter((item) => item.type === 'movie').length;
  const tvCount = items.filter((item) => item.type === 'tv').length;
  return {
    itemCount: items.length,
    movieCount,
    tvCount,
  };
}

export function toDetailTitle(item: MediaDetailDto) {
  return item.display_title || item.title;
}
