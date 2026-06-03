export type SourceType = 'html' | 'pdf' | 'markdown';
export type AssetType = 'html' | 'pdf' | 'markdown';

export interface Category {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
}

export interface Tag {
  id: number;
  name: string;
  slug: string;
}

export interface NewsletterAsset {
  asset_type: AssetType;
  content_url: string;
  download_url: string;
  is_primary: boolean;
  file_path?: string | null;
}

export interface NewsletterItem {
  id: number;
  title: string;
  slug: string;
  description?: string | null;
  source_type: SourceType;
  thumbnail_url?: string | null;
  thumbnail_path?: string | null;
  published_at?: string | null;
  category?: Category | null;
  tags: Tag[];
  available_assets: NewsletterAsset[];
}

export type NewsletterListItem = NewsletterItem;

export interface NewsletterDetail extends NewsletterItem {
  summary?: string | null;
  markdown_file_path?: string | null;
  default_asset_type: AssetType;
  is_active?: boolean;
  source_file_path?: string | null;
  source_identifier?: string;
  markdown_body?: string | null;
}

export interface NewsletterCalendarEntry {
  date: string;
  slug: string;
  title: string;
  source_type: SourceType;
}

export interface AuthResponse {
  user: {
    id: number;
    username: string;
    role: string;
    email?: string | null;
    is_active: boolean;
  };
  csrf_token: string;
}

export interface SyncResponse {
  created: number;
  updated: number;
  deactivated: number;
  skipped: number;
  issues: number;
}

export interface ReadEventRow {
  newsletter_id: number;
  client_ip: string;
  read_count: number;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface NewsletterReadSummary {
  newsletter_id: number;
  title: string;
  slug: string;
  total_reads: number;
  unique_ips: number;
}

export interface ReadEventsResponse {
  summaries: NewsletterReadSummary[];
  events: ReadEventRow[];
  loopback_only: boolean;
}
