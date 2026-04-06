export interface ApiSuccessResponse<T> {
  success: true;
  message: string;
  data: T;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorPayload;
}

export interface CategoryTreeNode {
  path: string;
  name: string;
  has_children?: boolean;
  media_count_hint?: number;
  category_count_hint?: number;
}

export interface CategoryTreeDto {
  path: string;
  parent_path: string | null;
  root: string;
  children: CategoryTreeNode[];
  skip_directories: string[];
}

export interface MediaListItemDto {
  id: number;
  tmdb_id: string | number | null;
  title: string;
  display_title: string | null;
  original_title: string | null;
  year: string | number | null;
  type: string | null;
  overview: string | null;
  vote_average: number | null;
  poster_url: string | null;
  backdrop_url: string | null;
  release_date: string | null;
  category_label: string | null;
  category_path: string | null;
  openlist_path: string | null;
  openlist_url: string | null;
  updated_at: string | null;
}

export interface AppSettingsFieldString {
  value: string;
  kind: 'string';
}

export interface MediaFileDto {
  name: string;
  path: string;
  openlist_url?: string | null;
  playable_url?: string | null;
}

export interface PlayLinkDto {
  path: string;
  playable_url?: string | null;
}

export interface MediaSeasonDto {
  season_number: number;
  name: string | null;
  episodes: MediaFileDto[];
}

export interface MediaDetailDto extends MediaListItemDto {
  genres: string[];
  file_count: number;
  season_count: number;
  episode_count: number;
  playable_url?: string | null;
  files: MediaFileDto[];
  seasons: MediaSeasonDto[];
}

export interface PaginationDto {
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
}

export interface MediaListResponseDto {
  items: MediaListItemDto[];
  years: number[];
  pagination: PaginationDto;
}

export interface RefreshResponseDto {
  category_path: string;
  category_name: string | null;
  item_count: number;
  failed_path_count: number;
  cache_hit: boolean;
  media_id?: number | null;
  media_path?: string | null;
  openlist_refreshed?: boolean;
}

export interface AccessLoginResponseDto {
  role: 'admin' | 'visitor';
}

export interface AppSettingsDto {
  openlist: {
    base_url: string;
    token: string;
    username: string;
    password: string;
    hash_login: boolean;
  };
  tmdb: {
    read_access_token: string;
    api_key: string;
    language: string;
  };
  media_wall: {
    media_root: string;
    output: string;
    site_dir: string;
    port: number;
    item_url_template: string;
    database_path: string;
    cache_ttl_seconds: number;
    refresh_cron: string;
    list_retry_count: number;
    retry_delay_seconds: number;
    skip_failed_directories: boolean;
    skip_directories: string[];
  };
  backend: {
    host: string;
    port: number;
    api_prefix: string;
    admin_token: string;
    cors: {
      allow_origins: string[];
      allow_methods: string[];
      allow_headers: string[];
    };
  };
  frontend: {
    site_url: string;
    dev_server_url: string;
    dist_dir: string;
    reverse_proxy_api_prefix: string;
    admin_passcode: string;
    visitor_passcode: string;
  };
  tests: {
    openlist: { path: string };
    tmdb: { query: string };
  };
}

export interface PlayHistoryDto {
  id: number;
  media_id: number;
  media_title: string;
  media_type: string | null;
  poster_url: string | null;
  played_at: number;
  vote_average?: number | null;
}

export interface MediaListQuery {
   categoryPath?: string;
   includeDescendants?: boolean;
   year?: number;
   keyword?: string;
   type?: string;
   page?: number;
   pageSize?: number;
}
