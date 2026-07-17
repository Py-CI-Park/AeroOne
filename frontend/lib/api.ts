import type {
  AdminOverviewResponse,
  AuthActivityResponse,
  AdminUser,
  AdminGroup,
  AssetHealthResponse,
  ConfigHealthResponse,
  AuditEvent,
  BackupRecord,
  BackupRestoreDryRun,
  AiAdminStatus,
  AiChatMessage,
  AiChatResponse,
  AiConversationDetail,
  AiConversationListResponse,
  AiConversationSummary,
  AiStatusResponse,
  AssetType,
  AuthResponse,
  Category,
  ClientSession,
  CollectionSearchResponse,
  ConnectedUsersResponse,
  ChartGenerateResponse,
  ChartInspectResponse,
  ChartType,
  ChartManualSpecInput,
  OfficeJobDetail,
  OfficeJobListResponse,
  DiagramGenerateRequest,
  DiagramGenerateResponse,
  OfficeSample,
  LeantimeHealth,
  LeantimeProject,
  LeantimeTask,
  LeantimeCalendarEntry,
  LeantimeReadResponse,
  DocumentListItem,
  ReportGenerateResponse,
  LlmConnection,
  LlmConnectionCreatePayload,
  LlmConnectionUpdatePayload,
  LlmVerifyResponse,
  NewsletterCalendarEntry,
  NewsletterDetail,
  NewsletterItem,
  ReadEventsResponse,
  Permission,
  RbacMatrixUser,
  ResourceGrant,
  SyncResponse,
  ServiceModule,
  SessionPurgeResponse,
  Tag,
  UnifiedSearchResult,
} from '@/lib/types';
import { buildNewsletterProxyPath, loggedServerFetchJson } from '@/lib/newsletter-observability';

const SERVER_BASE = process.env.SERVER_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:18437';
const BROWSER_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:18437';

export function getServerApiBase() {
  return SERVER_BASE.trim().replace(/\/$/, '');
}

export function getBrowserApiBase() {
  return BROWSER_BASE.trim().replace(/\/$/, '');
}

export function getNewsletterProxyPath(path: string) {
  return buildNewsletterProxyPath(path);
}
const OFFICE_TOOLS_BACKEND_PREFIX = '/api/v1/office-tools/';
const OFFICE_TOOLS_PROXY_PREFIX = '/api/frontend/office-tools/';
const OFFICE_TOOLS_DOWNLOAD_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{3,64}\/(?:bundle|artifacts\/[A-Za-z0-9-][A-Za-z0-9._-]*)$/;

export function getOfficeArtifactProxyPath(path: string) {
  if (!OFFICE_TOOLS_DOWNLOAD_PATH.test(path)) {
    throw new Error('Only office-tools artifact paths can be proxied');
  }
  return `${OFFICE_TOOLS_PROXY_PREFIX}${path.slice(OFFICE_TOOLS_BACKEND_PREFIX.length)}`;
}

function encodeOfficeJobId(jobId: string) {
  if (!/^[0-9a-f]{32}$/.test(jobId)) {
    throw new Error('Invalid office job ID');
  }
  return encodeURIComponent(jobId);
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// 백엔드 원문 응답 본문을 절대 노출하지 않는 안전한 한국어 카테고리 메시지.
// UI 컴포넌트가 동일한 매핑을 재사용할 수 있도록 export 한다.
export function getSafeApiErrorMessage(status: number): string {
  if (status === 401) return '로그인이 필요합니다';
  if (status === 403) return '접근 권한이 없습니다';
  if (status === 422) return '요청 형식이 올바르지 않습니다';
  if (status === 429) return '요청이 너무 잦습니다';
  if (status >= 500) return '서버 오류가 발생했습니다';
  return '요청 처리에 실패했습니다';
}

async function browserFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    cache: 'no-store',
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new ApiError(getSafeApiErrorMessage(response.status), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}



export async function fetchClientSession(): Promise<ClientSession> {
  const response = await fetch('/api/frontend/session', {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new ApiError(getSafeApiErrorMessage(response.status), response.status);
  }
  return (await response.json()) as ClientSession;
}

// 자기 자신의 활동 요약. same-origin BFF 를 통해 쿠키만으로 조회하며
// query/body/클라이언트 사용자 ID 를 절대 보내지 않는다(계약: 422 방어는 백엔드 몫).
export async function fetchAuthActivity(): Promise<AuthActivityResponse> {
  return browserFetch<AuthActivityResponse>('/api/frontend/auth/activity');
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
    throw new ApiError(text || `Failed to load document: ${response.status}`, response.status);
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
    throw new ApiError(text || `Failed to load collection list: ${response.status}`, response.status);
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

export async function fetchCollectionSearch(params: {
  q: string;
  collections?: Array<'document' | 'civil' | 'nsa'>;
  limit?: number;
}): Promise<CollectionSearchResponse> {
  const query = new URLSearchParams();
  query.set('q', params.q);
  if (params.collections?.length) {
    query.set('collections', params.collections.join(','));
  }
  if (params.limit != null) {
    query.set('limit', String(params.limit));
  }
  const response = await fetch(`/api/frontend/collections/search?${query.toString()}`, { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Failed to search collections: ${response.status}`);
  }
  return (await response.json()) as CollectionSearchResponse;
}

export async function fetchAiStatus(): Promise<AiStatusResponse> {
  const response = await fetch('/api/frontend/ai/status', { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text();
    try {
      return JSON.parse(text) as AiStatusResponse;
    } catch {
      throw new Error(text || `Failed to load AI status: ${response.status}`);
    }
  }
  return (await response.json()) as AiStatusResponse;
}

export async function sendAiChat(payload: {
  messages: AiChatMessage[];
  use_search?: boolean;
  collections?: Array<'document' | 'civil' | 'nsa'>;
  limit?: number;
  conversation_id?: number | null;
  temporary?: boolean;
  selected_refs?: Array<{ collection: 'document' | 'civil' | 'nsa'; path: string }>;
}, options?: { signal?: AbortSignal }): Promise<AiChatResponse> {
  const response = await fetch('/api/frontend/ai/chat', {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `AI request failed: ${response.status}`);
  }
  return (await response.json()) as AiChatResponse;
}

export async function listAiConversations(includeArchived = false): Promise<AiConversationListResponse> {
  const query = includeArchived ? '?include_archived=true' : '';
  const response = await fetch(`/api/frontend/ai/conversations${query}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Failed to load conversations: ${response.status}`);
  }
  return (await response.json()) as AiConversationListResponse;
}

export async function getAiConversation(id: number): Promise<AiConversationDetail> {
  const response = await fetch(`/api/frontend/ai/conversations/${id}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Failed to load conversation: ${response.status}`);
  }
  return (await response.json()) as AiConversationDetail;
}

export async function updateAiConversation(
  id: number,
  patch: { title?: string; is_pinned?: boolean; is_archived?: boolean },
): Promise<AiConversationSummary> {
  const response = await fetch(`/api/frontend/ai/conversations/${id}`, {
    method: 'PATCH',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(`Failed to update conversation: ${response.status}`);
  }
  return (await response.json()) as AiConversationSummary;
}

export async function deleteAiConversation(id: number): Promise<void> {
  const response = await fetch(`/api/frontend/ai/conversations/${id}`, {
    method: 'DELETE',
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`);
  }
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


export async function login(username: string, password: string) {
  return browserFetch<AuthResponse>('/api/frontend/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}
export async function logout() {
  return browserFetch<{ status: string }>('/api/frontend/auth/logout', {
    method: 'POST',
  });
}


export async function fetchPublicServiceModules(cookieHeader?: string) {
  return loggedServerFetchJson<ServiceModule[]>({
    label: 'service-modules.public',
    baseUrl: getServerApiBase(),
    path: '/api/v1/admin/service-modules/public',
    init: cookieHeader ? { headers: { cookie: cookieHeader } } : undefined,
  });
}

export async function fetchAdminOverview() {
  return browserFetch<AdminOverviewResponse>('/api/frontend/admin/overview', { method: 'GET' });
}


export async function fetchConnectedUsers() {
  return browserFetch<ConnectedUsersResponse>('/api/frontend/admin/sessions', { method: 'GET' });
}

export async function purgeSessions(csrfToken: string) {
  return browserFetch<SessionPurgeResponse>('/api/frontend/admin/sessions/purge', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchAdminUsers() {
  return browserFetch<AdminUser[]>('/api/frontend/admin/users', { method: 'GET' });
}

export async function fetchAdminPermissions() {
  return browserFetch<Permission[]>('/api/frontend/admin/permissions', { method: 'GET' });
}

export async function createAdminUser(payload: { username: string; password: string; role: string; display_name?: string | null; email?: string | null; is_active?: boolean }, csrfToken: string) {
  return browserFetch<AdminUser>('/api/frontend/admin/users', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function updateAdminUser(id: number, payload: Partial<Pick<AdminUser, 'display_name' | 'email' | 'role' | 'is_active'>> & { permissions?: string[] }, csrfToken: string) {
  return browserFetch<AdminUser>(`/api/frontend/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function resetAdminUserPassword(id: number, temporaryPassword: string, csrfToken: string) {
  return browserFetch<AdminUser>(`/api/frontend/admin/users/${id}/password-reset`, {
    method: 'POST',
    body: JSON.stringify({ temporary_password: temporaryPassword }),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchAdminGroups() {
  return browserFetch<AdminGroup[]>('/api/frontend/admin/groups', { method: 'GET' });
}

export async function upsertAdminGroup(payload: { key: string; name: string; description?: string | null; is_active: boolean; permissions: string[] }, csrfToken: string) {
  return browserFetch<AdminGroup>('/api/frontend/admin/groups', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}


export async function fetchRbacMatrix() {
  return browserFetch<RbacMatrixUser[]>('/api/frontend/admin/rbac-matrix', { method: 'GET' });
}

export async function listResourceGrants(subject?: { subject_type: 'user' | 'group'; subject_id: number }) {
  const query = subject ? `?${new URLSearchParams({ subject_type: subject.subject_type, subject_id: String(subject.subject_id) }).toString()}` : '';
  return browserFetch<ResourceGrant[]>(`/api/frontend/admin/resource-grants${query}`, { method: 'GET' });
}

export async function createResourceGrant(payload: Omit<ResourceGrant, 'id' | 'created_at'>, csrfToken: string) {
  return browserFetch<ResourceGrant>('/api/frontend/admin/resource-grants', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function deleteResourceGrant(id: number, csrfToken: string) {
  return browserFetch<void>(`/api/frontend/admin/resource-grants/${id}`, {
    method: 'DELETE',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function addUserGroup(userId: number, groupId: number, csrfToken: string) {
  return browserFetch<AdminUser>(`/api/frontend/admin/users/${userId}/groups/${groupId}`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function removeUserGroup(userId: number, groupId: number, csrfToken: string) {
  return browserFetch<AdminUser>(`/api/frontend/admin/users/${userId}/groups/${groupId}`, {
    method: 'DELETE',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchAuditEvents() {
  return browserFetch<AuditEvent[]>('/api/frontend/admin/audit-events', { method: 'GET' });
}

export async function fetchServiceModulesAdmin() {
  return browserFetch<ServiceModule[]>('/api/frontend/admin/service-modules', { method: 'GET' });
}

export async function updateServiceModule(id: number, payload: Partial<ServiceModule>, csrfToken: string) {
  return browserFetch<ServiceModule>(`/api/frontend/admin/service-modules/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function createServiceModule(payload: Partial<ServiceModule> & { key: string; title: string }, csrfToken: string) {
  return browserFetch<ServiceModule>('/api/frontend/admin/service-modules', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function deleteServiceModule(id: number, csrfToken: string) {
  return browserFetch<void>(`/api/frontend/admin/service-modules/${id}`, {
    method: 'DELETE',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function changeOwnPassword(currentPassword: string, newPassword: string, csrfToken: string) {
  return browserFetch<AuthResponse>('/api/frontend/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchAssetHealth() {
  return browserFetch<AssetHealthResponse>('/api/frontend/admin/newsletters/assets/health', { method: 'GET' });
}

export async function fetchConfigHealth() {
  return browserFetch<ConfigHealthResponse>('/api/frontend/admin/config/health', { method: 'GET' });
}

export async function bulkUpdateNewsletters(ids: number[], action: 'publish' | 'archive' | 'draft', csrfToken: string) {
  return browserFetch<{ updated: number }>('/api/frontend/admin/newsletters/bulk', {
    method: 'POST',
    body: JSON.stringify({ ids, action }),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchBackups() {
  return browserFetch<BackupRecord[]>('/api/frontend/admin/backups', { method: 'GET' });
}

export async function createBackup(csrfToken: string) {
  return browserFetch<BackupRecord>('/api/frontend/admin/backups', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function validateBackup(id: number, csrfToken: string) {
  return browserFetch<{ filename: string; valid: boolean; issues: string[] }>(
    `/api/frontend/admin/backups/${id}/validate`,
    {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrfToken },
    },
  );
}

export async function dryRunRestoreBackup(id: number, csrfToken: string) {
  return browserFetch<BackupRestoreDryRun>(`/api/frontend/admin/backups/${id}/restore/dry-run`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchAdminAiStatus() {
  return browserFetch<AiAdminStatus>('/api/frontend/admin/ai/status', { method: 'GET' });
}

export async function fetchUnifiedSearch(q: string, includeNsa = false) {
  const query = new URLSearchParams({ q, include_nsa: includeNsa ? 'true' : 'false' });
  return browserFetch<{ query: string; results: UnifiedSearchResult[]; degraded: boolean; reason?: string }>(
    `/api/frontend/search/unified?${query.toString()}`,
    { method: 'GET' },
  );
}
export async function fetchAdminNewsletters() {
  return browserFetch<NewsletterItem[]>('/api/frontend/admin/newsletters', { method: 'GET' });
}

export async function fetchAdminNewsletterDetail(id: number) {
  return browserFetch<NewsletterDetail>(`/api/frontend/admin/newsletters/${id}`, { method: 'GET' });
}

export async function createNewsletter(payload: Record<string, unknown>, csrfToken: string) {
  return browserFetch<NewsletterDetail>('/api/frontend/admin/newsletters', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function updateNewsletter(id: number, payload: Record<string, unknown>, csrfToken: string) {
  return browserFetch<NewsletterDetail>(`/api/frontend/admin/newsletters/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function uploadThumbnail(id: number, formData: FormData, csrfToken: string) {
  return browserFetch<{ thumbnail_path: string }>(`/api/frontend/admin/newsletters/${id}/thumbnail`, {
    method: 'POST',
    body: formData,
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function syncNewsletters(csrfToken: string) {
  return browserFetch<SyncResponse>('/api/frontend/admin/newsletters/sync', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchCategories() {
  return browserFetch<Category[]>('/api/frontend/admin/categories', { method: 'GET' });
}

export async function createCategory(payload: { name: string; description?: string | null; sort_order?: number; is_active?: boolean }, csrfToken: string) {
  return browserFetch<Category>('/api/frontend/admin/categories', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function updateCategory(id: number, payload: Partial<Category>, csrfToken: string) {
  return browserFetch<Category>(`/api/frontend/admin/categories/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchTags() {
  return browserFetch<Tag[]>('/api/frontend/admin/tags', { method: 'GET' });
}

export async function createTag(payload: { name: string; sort_order?: number; is_active?: boolean }, csrfToken: string) {
  return browserFetch<Tag>('/api/frontend/admin/tags', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function updateTag(id: number, payload: Partial<Tag>, csrfToken: string) {
  return browserFetch<Tag>(`/api/frontend/admin/tags/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

// 읽음 비콘 — 예외적으로 same-origin 프록시를 거치지 않고 브라우저가 백엔드를 직접 호출해야 한다.
// 백엔드가 request.client.host 로 LAN 독자 IP 를 기록하기 때문이며, 프록시/SSR 경로는 Next 서버 IP 로 퇴화한다.
// body 없음. sendBeacon 우선(페이지 이탈에도 전송 보장),
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
  return browserFetch<ReadEventsResponse>(`/api/frontend/admin/read-events${qs ? `?${qs}` : ''}`, { method: 'GET' });
}

export async function purgeReadEvents(csrfToken: string, newsletterId?: number) {
  const query = newsletterId != null ? `?newsletter_id=${newsletterId}` : '';
  return browserFetch<{ deleted: number }>(`/api/frontend/admin/read-events/purge${query}`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

// AeroOne v1.14.0 AI 제공자(Provider) 설정 계약.
// 백엔드 안전 DTO(app/modules/admin/schemas.py)와 1:1로 대응하는 평면(flat) 구조만 사용한다.
// canonical_url/credential_ref/credential_binding_version 은 서버가 절대 응답으로 내려주지
// 않는다 — GET 응답에는 표시용 compatible_display_url 만 존재한다. 스테이징(설정 저장/회전)
// 직후에만, 방금 사용자가 입력한 canonical_url/model/generation 값을 폼에 유지해 두었다가
// (평문 API 키는 제외) "저장 설정 테스트" 호출에 그대로 재사용한다.
export type AiProviderKind = 'ollama' | 'openai_compatible';
export type AiProviderCompatibleState = 'absent' | 'unverified' | 'verified';

export interface AiProviderConfigResponse {
  selected_kind: AiProviderKind;
  compatible_state: AiProviderCompatibleState;
  compatible_display_url: string | null;
  compatible_model: string | null;
  compatible_generation: string | null;
  compatible_test_proof_at: string | null;
  compatible_test_proof_model: string | null;
  config_version: number;
  updated_at: string;
}

export interface AiProviderTestResultResponse {
  success: boolean;
  reason_code: string | null;
  tested_at: string;
  canonical_url: string;
  model: string;
  generation: string;
}

export interface AiProviderReconcileResponse {
  reconciled: boolean;
  compatible_state: AiProviderCompatibleState;
  config_version: number;
}

// 실패한 연동 테스트의 reason_code 는 egress 계층(app/modules/ai/egress_transport.py)의
// 고정 안전 카테고리 값이다. 원문 예외 메시지는 절대 내려오지 않는다.
const AI_PROVIDER_TEST_REASON_LABELS: Record<string, string> = {
  'url-invalid': '연동 테스트 실패: URL 형식이 올바르지 않습니다',
  'url-unsafe-component': '연동 테스트 실패: URL에 허용되지 않는 구성요소가 있습니다',
  'scheme-not-allowed': '연동 테스트 실패: 허용되지 않는 URL 스킴입니다',
  'host-invalid': '연동 테스트 실패: 호스트가 올바르지 않습니다',
  'host-ambiguous': '연동 테스트 실패: 호스트를 특정할 수 없습니다',
  'port-not-allowed': '연동 테스트 실패: 허용되지 않는 포트입니다',
  'peer-policy-denied': '연동 테스트 실패: 대상 접속이 정책에 의해 차단되었습니다',
  'dns-resolution-failed': '연동 테스트 실패: DNS 확인에 실패했습니다',
  'peer-equality-failed': '연동 테스트 실패: 접속 대상 검증에 실패했습니다',
  'tls-verification-failed': '연동 테스트 실패: TLS 인증서 검증에 실패했습니다',
  'connect-failed': '연동 테스트 실패: 연결할 수 없습니다',
  'redirect-rejected': '연동 테스트 실패: 리디렉션이 거부되었습니다',
  'request-too-large': '연동 테스트 실패: 요청 크기가 너무 큽니다',
  'response-too-large': '연동 테스트 실패: 응답 크기가 너무 큽니다',
  'invalid-json': '연동 테스트 실패: 응답이 올바른 JSON 형식이 아닙니다',
  'http-error': '연동 테스트 실패: 원격 서버 오류가 반환되었습니다',
  'upstream-shape-invalid': '연동 테스트 실패: 응답 형식이 예상과 다릅니다',
};

// 백엔드가 반환하는 reason_code 는 이미 고정된 안전 카테고리이지만, 알 수 없는 값이
// 오더라도 원문을 그대로 노출하지 않고 방어적으로 매핑한다.
export function getSafeAiProviderReasonMessage(code: string | null | undefined): string {
  if (!code) return '연동 테스트 성공';
  return AI_PROVIDER_TEST_REASON_LABELS[code] ?? '알 수 없는 상태입니다. 관리자에게 문의하세요.';
}

export async function fetchAiProviderConfig() {
  return browserFetch<AiProviderConfigResponse>('/api/frontend/admin/ai-provider/config', { method: 'GET' });
}

// 설정 저장/회전: URL/모델/세대/키를 스테이징한다. 성공 시 compatible_state 는 'unverified'
// 로 전환되고(테스트 증빙은 즉시 무효화), 이전에 openai_compatible 이 선택되어 있었다면
// 서버가 자동으로 'ollama' 로 되돌린다(입증되지 않은 바인딩으로는 절대 트래픽을 흘리지 않음).
export async function stageAiProviderCompatibleConfig(
  payload: { canonical_url: string; display_url: string; model: string; generation: string; api_key: string; expected_config_version: number },
  csrfToken: string,
) {
  return browserFetch<AiProviderConfigResponse>('/api/frontend/admin/ai-provider/config', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

// === LLM 연결 레지스트리 (산출물 A) — /api/v1/admin/llm-connections 를 admin 프록시로 중계 ===

export async function fetchLlmConnections() {
  return browserFetch<LlmConnection[]>('/api/frontend/admin/llm-connections', { method: 'GET' });
}

export async function createLlmConnection(payload: LlmConnectionCreatePayload, csrfToken: string) {
  return browserFetch<LlmConnection>('/api/frontend/admin/llm-connections', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

// 저장 설정 테스트는 직전 스테이징 값과 정확히 일치하는
// canonical_url/model/generation만 보내며, 서버가 DPAPI 저장소의 키를 사용한다.
export async function testAiProviderStagedConfig(
  payload: { canonical_url: string; model: string; generation: string },
  csrfToken: string,
) {
  return browserFetch<AiProviderTestResultResponse>('/api/frontend/admin/ai-provider/test', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function updateLlmConnection(id: number, payload: LlmConnectionUpdatePayload, csrfToken: string) {
  return browserFetch<LlmConnection>(`/api/frontend/admin/llm-connections/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function activateAiProviderCompatible(expectedConfigVersion: number, csrfToken: string) {
  return browserFetch<AiProviderConfigResponse>('/api/frontend/admin/ai-provider/activate', {
    method: 'POST',
    body: JSON.stringify({ expected_config_version: expectedConfigVersion }),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function selectAiProviderKind(kind: AiProviderKind, expectedConfigVersion: number, csrfToken: string) {
  return browserFetch<AiProviderConfigResponse>('/api/frontend/admin/ai-provider/selection', {
    method: 'POST',
    body: JSON.stringify({ selected_kind: kind, expected_config_version: expectedConfigVersion }),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function deleteAiProviderCredential(expectedConfigVersion: number, csrfToken: string) {
  return browserFetch<AiProviderConfigResponse>('/api/frontend/admin/ai-provider/credential', {
    method: 'DELETE',
    body: JSON.stringify({ expected_config_version: expectedConfigVersion }),
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function deleteLlmConnection(id: number, csrfToken: string) {
  return browserFetch<void>(`/api/frontend/admin/llm-connections/${id}`, {
    method: 'DELETE',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function reconcileAiProviderConfig(csrfToken: string) {
  return browserFetch<AiProviderReconcileResponse>('/api/frontend/admin/ai-provider/reconcile', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function setDefaultLlmConnection(id: number, csrfToken: string) {
  return browserFetch<LlmConnection>(`/api/frontend/admin/llm-connections/${id}/default`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function verifyLlmConnection(id: number, csrfToken: string) {
  return browserFetch<LlmVerifyResponse>(`/api/frontend/admin/llm-connections/${id}/verify`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchLlmConnectionModels(id: number) {
  return browserFetch<LlmVerifyResponse>(`/api/frontend/admin/llm-connections/${id}/models`, { method: 'GET' });
}

// office-tools 소유자별 작업 이력: 목록은 usage와 함께, 상세는 검증된 job ID로 조회한다.
export async function fetchOfficeJobs(): Promise<OfficeJobListResponse> {
  return browserFetch<OfficeJobListResponse>('/api/frontend/office-tools/jobs', { method: 'GET' });
}

export async function fetchOfficeJob(jobId: string): Promise<OfficeJobDetail> {
  return browserFetch<OfficeJobDetail>(`/api/frontend/office-tools/jobs/${encodeOfficeJobId(jobId)}`, { method: 'GET' });
}

// office-tools 다이어그램 스튜디오: 설명 → Mermaid 소스. 렌더는 브라우저에서 한다.
export async function generateDiagram(payload: DiagramGenerateRequest, csrfToken: string, signal?: AbortSignal) {
  return browserFetch<DiagramGenerateResponse>('/api/frontend/office-tools/diagrams/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'X-CSRF-Token': csrfToken },
    signal,
  });
}

// office-tools 보고서 스튜디오: Markdown 파일(+이미지/ZIP) 업로드 → sanitize HTML 보고서.
// multipart FormData 를 그대로 전달한다(browserFetch 가 FormData 면 Content-Type 을 생략).
export interface ReportGenerateInput {
  markdownFile: File;
  assets?: File[];
  title?: string;
  subtitle?: string;
  documentVersion?: string;
  tags?: string;
  aiMode?: 'none' | 'polish' | 'executive';
}

export async function generateReport(input: ReportGenerateInput, csrfToken: string, signal?: AbortSignal) {
  const form = new FormData();
  form.append('markdown_file', input.markdownFile);
  for (const asset of input.assets ?? []) {
    form.append('assets', asset);
  }
  form.append('title', input.title ?? '');
  form.append('subtitle', input.subtitle ?? '');
  form.append('document_version', input.documentVersion ?? '');
  form.append('tags', input.tags ?? '');
  form.append('ai_mode', input.aiMode ?? 'none');
  return browserFetch<ReportGenerateResponse>('/api/frontend/office-tools/reports/generate', {
    method: 'POST',
    body: form,
    headers: { 'X-CSRF-Token': csrfToken },
    signal,
  });
}

// office-tools 차트 스튜디오: 데이터 파일 → 프로필. job 을 만들지 않고 미리보기만 돌려준다.
export async function inspectChartData(dataFile: File, csrfToken: string, signal?: AbortSignal) {
  const form = new FormData();
  form.append('data_file', dataFile);
  return browserFetch<ChartInspectResponse>('/api/frontend/office-tools/charts/inspect', {
    method: 'POST',
    body: form,
    headers: { 'X-CSRF-Token': csrfToken },
    signal,
  });
}

// office-tools 차트 스튜디오: 데이터 + 목적 → ECharts option. 렌더는 브라우저에서 한다.
export interface ChartGenerateInput {
  dataFile: File;
  prompt?: string;
  aiAssist?: boolean;
  chartType?: ChartType | '';
  manualSpec?: ChartManualSpecInput;
  manualSpecJson?: string;
  // 후속 명령: 직전 성공 결과의 result.chart_spec 을 그대로 넘긴다. manualSpec 이 있으면
  // 서버가 manualSpec 을 우선 처리하므로 프런트는 둘을 동시에 채우지 않는다.
  previousSpec?: Record<string, unknown>;
}

export async function generateChart(input: ChartGenerateInput, csrfToken: string, signal?: AbortSignal) {
  if (input.manualSpec !== undefined && input.manualSpecJson !== undefined) {
    throw new Error('Provide either manualSpec or manualSpecJson, not both');
  }

  const manualSpecJson = input.manualSpec !== undefined ? JSON.stringify(input.manualSpec) : input.manualSpecJson;
  const form = new FormData();
  form.append('data_file', input.dataFile);
  form.append('prompt', input.prompt ?? '');
  form.append('ai_assist', String(input.aiAssist ?? true));
  if (input.chartType) form.append('chart_type', input.chartType);
  if (manualSpecJson) form.append('manual_spec_json', manualSpecJson);
  if (input.previousSpec !== undefined) form.append('previous_spec_json', JSON.stringify(input.previousSpec));
  return browserFetch<ChartGenerateResponse>('/api/frontend/office-tools/charts/generate', {
    method: 'POST',
    body: form,
    headers: { 'X-CSRF-Token': csrfToken },
    signal,
  });
}

// office-tools 샘플 예제: 도구별 여러 종의 내용 + 폼 프리필 힌트를 한 번에 받아온다.
// 프런트는 이 목록을 도구별 '예제' 칩으로 보여 주고, 고르면 해당 내용으로 폼을 채운다.
export async function fetchOfficeSamples(): Promise<OfficeSample[]> {
  return browserFetch<OfficeSample[]>('/api/frontend/office-tools/samples', { method: 'GET' });
}

// Leantime 동거 스택의 기동 여부를 실시간으로 조회한다. 랜딩 페이지가 '구동 중/미설치'를
// 구분해 '열기' 버튼을 조건부로 활성화하는 데 쓴다.
export async function fetchLeantimeHealth(): Promise<LeantimeHealth> {
  return browserFetch<LeantimeHealth>('/api/frontend/leantime/health', { method: 'GET' });
}


// Leantime 읽기 전용 대시보드 데이터 — same-origin 프록시(/api/frontend/leantime/*)를 거쳐
// 백엔드 /api/v1/leantime/* 를 호출한다. leantime.read 권한이 없으면 403, 세션이 없으면
// 401 로 실패하며, 그 외에는 degraded(reason) 로 부분/저하 상태를 알려준다.
export async function fetchLeantimeProjects(): Promise<LeantimeReadResponse<LeantimeProject>> {
  return browserFetch<LeantimeReadResponse<LeantimeProject>>('/api/frontend/leantime/projects', { method: 'GET' });
}

export async function fetchLeantimeTasks(): Promise<LeantimeReadResponse<LeantimeTask>> {
  return browserFetch<LeantimeReadResponse<LeantimeTask>>('/api/frontend/leantime/tasks', { method: 'GET' });
}

export async function fetchLeantimeCalendar(start: string, end: string): Promise<LeantimeReadResponse<LeantimeCalendarEntry>> {
  const query = new URLSearchParams({ start, end });
  return browserFetch<LeantimeReadResponse<LeantimeCalendarEntry>>(
    `/api/frontend/leantime/calendar?${query.toString()}`,
    { method: 'GET' },
  );
}
