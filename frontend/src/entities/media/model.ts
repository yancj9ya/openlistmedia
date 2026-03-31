import type { MediaDetailDto, MediaListItemDto } from '../../shared/api/types';

export interface MediaCardModel {
  id: number;
  title: string;
  subtitle: string;
  overview: string;
  posterUrl: string | null;
  typeLabel: string;
  yearLabel: string;
  ratingLabel: string;
  categoryLabel: string;
}

export function toMediaCardModel(item: MediaListItemDto): MediaCardModel {
  return {
    id: item.id,
    title: item.display_title || item.title,
    subtitle: item.original_title || '',
    overview: item.overview || '暂无简介',
    posterUrl: item.poster_url,
    typeLabel: item.type === 'tv' ? '剧集' : item.type === 'movie' ? '电影' : '未知类型',
    yearLabel: item.year ? String(item.year) : '-',
    ratingLabel: typeof item.vote_average === 'number' ? `${item.vote_average.toFixed(1)} / 10` : '暂无评分',
    categoryLabel: item.category_label || '未分类',
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