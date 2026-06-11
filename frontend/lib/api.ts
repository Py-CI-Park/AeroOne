import type {
  AssetType,
  AuthResponse,
  Category,
  DocumentListItem,
  NewsletterCalendarEntry,
  NewsletterDetail,
  NewsletterItem,
  ReadEventsResponse,
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
  return loggedServerFetchJson<NewsletterItem[]>({
    label: 'newsletters.list',
    baseUrl: getServerApiBase(),
    path: `/api/v1/newsletters${query}`,
  });
}

export async function fetchNewsletterDetail(slug: string) {
  return loggedServerFetchJson<NewsletterDetail>({
    label: 'newsletters.detail',
    baseUrl: getServerApiBase(),
    path: `/api/v1/newsletters/${slug}`,
  });
}

export async function fetchLatestNewsletter() {
  return loggedServerFetchJson<NewsletterDetail>({
    label: 'newsletters.latest',
    baseUrl: getServerApiBase(),
    path: '/api/v1/newsletters/latest',
  });
}

export async function fetchNewsletterCalendar() {
  return loggedServerFetchJson<NewsletterCalendarEntry[]>({
    label: 'newsletters.calendar',
    baseUrl: getServerApiBase(),
    path: '/api/v1/newsletters/calendar',
  });
}

export async function fetchNewsletterAssetContent(path: string) {
  return loggedServerFetchJson<{ asset_type: AssetType; content_html: string }>({
    label: 'newsletters.asset',
    baseUrl: getServerApiBase(),
    path,
  });
}

export async function fetchCivilAircraftReport() {
  // 민간 항공기 종합 분석 — 달력/DB 없이 _database/civil_aircraft 의 단일 HTML 을 서버에서
  // 받아 그대로 렌더한다. 보고서가 없으면 백엔드가 404 → 호출부(page)에서 catch 해 안내한다.
  return loggedServerFetchJson<{ asset_type: 'html'; content_html: string }>({
    label: 'reports.civil-aircraft',
    baseUrl: getServerApiBase(),
    path: '/api/v1/reports/civil-aircraft/content/html',
  });
}

export async function fetchDocumentList() {
  // 문서 보관소 목록 — _database/document 의 HTML 을 폴더 트리로 그리기 위한 메타(path/name/folder)만 받는다.
  // 콘텐츠는 선택 시 fetchDocumentContent 로 별도 요청한다. 폴더가 없으면 백엔드가 빈 목록을 준다.
  return loggedServerFetchJson<{ documents: DocumentListItem[] }>({
    label: 'documents.list',
    baseUrl: getServerApiBase(),
    path: '/api/v1/documents/list',
  });
}

export async function fetchCollectionContent(
  collection: string,
  path: string,
): Promise<{ asset_type: 'html'; content_html: string }> {
  // 컬렉션 본문 1개의 sanitize 된 HTML 을 same-origin 프록시 경유로 받는다.
  // getBrowserApiBase()/localhost 를 쓰지 않고 상대 경로만 사용해 외부 PC 에서도 동작한다.
  // 경로는 백엔드 path-guard 로 루트 밖 접근이 차단된다.
  const response = await fetch(
    `/api/frontend/collections/${collection}/content/html?path=${encodeURIComponent(path)}`,
    { cache: 'no-store' },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to load document: ${response.status}`);
  }
  return (await response.json()) as { asset_type: 'html'; content_html: string };
}

export function getCollectionDownloadPath(collection: string, path: string): string {
  // 브라우저가 same-origin 프록시를 통해 원본 HTML 을 첨부 다운로드하게 하는 URL.
  // collection 값은 프록시 라우트/백엔드 whitelist(document/civil/nsa)가 최종 검증한다.
  return `/api/frontend/collections/${encodeURIComponent(collection)}/download/html?path=${encodeURIComponent(path)}`;
}

export async function fetchCollectionList(collection: string): Promise<{ documents: DocumentListItem[] }> {
  // 컬렉션 목록 — NSA 언락 후 클라이언트에서 same-origin 프록시 경유로 받는다.
  const response = await fetch(`/api/frontend/collections/${collection}/list`, { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to load collection list: ${response.status}`);
  }
  return (await response.json()) as { documents: DocumentListItem[] };
}

export async function fetchCollectionListServer(collection: string): Promise<{ documents: DocumentListItem[] }> {
  // SSR 전용 — 서버에서 getServerApiBase() 를 직접 호출해 컬렉션 목록을 받는다(civil 페이지 SSR 등).
  return loggedServerFetchJson<{ documents: DocumentListItem[] }>({
    label: `collections.${collection}.list`,
    baseUrl: getServerApiBase(),
    path: `/api/v1/collections/${collection}/list`,
  });
}

export async function fetchDocumentContent(path: string): Promise<{ asset_type: 'html'; content_html: string }> {
  // fetchCollectionContent('document', path) 로 위임한다 — same-origin 프록시 경유.
  return fetchCollectionContent('document', path);
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

// 읽음 비콘 — 브라우저가 백엔드를 "직접" 호출해야 request.client.host 가 독자 LAN IP 가 된다
// (SSR/프록시 경로는 Next 서버 IP 로 퇴화). body 없음. sendBeacon 우선(페이지 이탈에도 전송 보장),
// 미지원 환경은 fetch keepalive 폴백. 실패는 읽기 경험에 영향 없으므로 조용히 무시한다.
export function recordNewsletterRead(newsletterId: number): void {
  const url = `${getBrowserApiBase()}/api/v1/newsletters/${newsletterId}/read`;
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      navigator.sendBeacon(url);
      return;
    }
  } catch {
    // sendBeacon 실패 시 fetch 폴백으로 넘어간다.
  }
  void fetch(url, { method: 'POST', keepalive: true, credentials: 'include' }).catch(() => {
    // 비콘 실패는 무시.
  });
}

export async function fetchAdminReadEvents(params?: { newsletter_id?: number; ip?: string }): Promise<ReadEventsResponse> {
  const query = new URLSearchParams();
  if (params?.newsletter_id != null) query.set('newsletter_id', String(params.newsletter_id));
  if (params?.ip) query.set('ip', params.ip);
  const qs = query.toString();
  return browserFetch<ReadEventsResponse>(`/api/v1/admin/read-events${qs ? `?${qs}` : ''}`, { method: 'GET' });
}

export async function purgeReadEvents(csrfToken: string, newsletterId?: number) {
  const query = newsletterId != null ? `?newsletter_id=${newsletterId}` : '';
  return browserFetch<{ deleted: number }>(`/api/v1/admin/read-events/purge${query}`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}
