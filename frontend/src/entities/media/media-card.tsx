import { Link, useLocation } from 'react-router-dom';
import { toMediaCardModel } from './model';
import type { MediaListItemDto } from '../../shared/api/types';

interface MediaCardProps {
  item: MediaListItemDto;
}

export function MediaCard({ item }: MediaCardProps) {
  const model = toMediaCardModel(item);
  const location = useLocation();

  return (
    <article className="media-card media-card-compact">
      <Link
        className="poster-link"
        to={`/media/${item.id}`}
        state={{ from: `${location.pathname}${location.search}` }}
      >
        <div className="poster" style={model.posterUrl ? { backgroundImage: `url(${model.posterUrl})` } : undefined}>
          {model.posterUrl ? null : 'NO POSTER'}
        </div>
      </Link>
      <div className="chip-row media-card-tags">
        <span className="chip">{model.categoryLabel}</span>
        <span className="chip">{model.yearLabel}</span>
        <span className="chip">{model.ratingLabel}</span>
      </div>
      <h3 className="media-card-title" title={model.title}>{model.title}</h3>
    </article>
  );
}