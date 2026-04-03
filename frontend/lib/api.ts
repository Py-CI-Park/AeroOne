import type {
  AuthResponse,
  Category,
  NewsletterCalendarEntry,
  NewsletterDetail,
  NewsletterItem,
  SyncResponse,
  Tag,
} from '@/lib/types';
import { buildNewsletterProxyPath, loggedServerFetchJson } from '@/lib/newsletter-observability';

const SERVER_BASE = process.env.SERVER_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:18437';
const BROWSER_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:18437';

export function getServerApiBase() {
  return SERVER_BASE.replace(/\/$/, '');
}

export function getBrowserApiBase() {
  return BROWSER_BASE.replace(/\/$/, '');
}

export function getNewsletterProxyPath(path: string) {
  return buildNewsletterProxyPath(path);
}

async function browserFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getBrowserApiBase()}${path}`, {
    credentials: 'include',
    cache: 'no-store',
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchNewsletters(params?: Record<string, string>) {
  const query = params ? `?${new URLSearchParams(params).toString()}` : '';
  const response = await fetch(`${getServerApiBase()}/api/v1/newsletters${query}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to load newsletters');
  }
  return (await response.json()) as NewsletterItem[];
}

export async function fetchNewsletterDetail(slug: string) {
  const response = await fetch(`${getServerApiBase()}/api/v1/newsletters/${slug}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to load newsletter detail');
  }
  return (await response.json()) as NewsletterDetail;
}

export async function fetchLatestNewsletter() {
  const response = await fetch(`${getServerApiBase()}/api/v1/newsletters/latest`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to load latest newsletter');
  }
  return (await response.json()) as NewsletterDetail;
}

export async function fetchNewsletterCalendar() {
  const response = await fetch(`${getServerApiBase()}/api/v1/newsletters/calendar`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to load newsletter calendar');
  }
  return (await response.json()) as NewsletterCalendarEntry[];
}

export async function getPublicNewsletters(): Promise<{ items: NewsletterItem[] }> {
  return { items: await fetchNewsletters() };
}

export async function getNewsletterDetail(slug: string): Promise<NewsletterDetail> {
  return fetchNewsletterDetail(slug);
}

export async function getHtmlContent(path: string): Promise<{ content_type: 'html' | 'markdown'; html: string }> {
  const response = await fetch(`${getBrowserApiBase()}${path}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('Failed to load html content');
  }
  const payload = (await response.json()) as { asset_type: 'html' | 'markdown'; content_html: string };
  return { content_type: payload.asset_type, html: payload.content_html };
}

export async function login(username: string, password: string) {
  return browserFetch<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export async function fetchAdminNewsletters() {
  return browserFetch<NewsletterItem[]>('/api/v1/admin/newsletters', { method: 'GET' });
}

export async function fetchAdminNewsletterDetail(id: number) {
  return browserFetch<NewsletterDetail>(`/api/v1/admin/newsletters/${id}`, { method: 'GET' });
}

export async function createNewsletter(payload: Record<string, unknown>, csrfToken: string) {
  return browserFetch<NewsletterDetail>('/api/v1/admin/newsletters', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function updateNewsletter(id: number, payload: Record<string, unknown>, csrfToken: string) {
  return browserFetch<NewsletterDetail>(`/api/v1/admin/newsletters/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function uploadThumbnail(id: number, formData: FormData, csrfToken: string) {
  return browserFetch<{ thumbnail_path: string }>(`/api/v1/admin/newsletters/${id}/thumbnail`, {
    method: 'POST',
    body: formData,
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function syncNewsletters(csrfToken: string) {
  return browserFetch<SyncResponse>('/api/v1/admin/newsletters/sync', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchCategories() {
  return browserFetch<Category[]>('/api/v1/admin/categories', { method: 'GET' });
}

export async function fetchTags() {
  return browserFetch<Tag[]>('/api/v1/admin/tags', { method: 'GET' });
}
