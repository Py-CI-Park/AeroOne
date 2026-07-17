export type SourceType = 'html' | 'pdf' | 'markdown';
export type AssetType = 'html' | 'pdf' | 'markdown';

export interface Category {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  sort_order?: number;
  is_active?: boolean;
}

export interface Tag {
  id: number;
  name: string;
  slug: string;
  sort_order?: number;
  is_active?: boolean;
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
  status?: string;
  status_changed_at?: string | null;
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

export interface ClientSessionResourceGrant {
  resource_type: string;
  resource_id: string;
  permission_key: string;
}

export interface ClientSession {
  authenticated: boolean | null;
  username: string | null;
  role: string | null;
  is_admin: boolean;
  can_view_document: boolean;
  can_view_nsa: boolean;
  can_use_ai: boolean;
  permissions: string[];
  resources: ClientSessionResourceGrant[];
}

export interface AuthActivityIdentity {
  username: string;
  display_name: string | null;
  role: 'admin' | 'user' | 'pending';
}

export interface AuthActivitySession {
  state: 'current' | 'active';
  last_activity_at: string;
  device_label: '현재 기기' | '다른 활성 기기';
}

export interface AuthActivityEvent {
  kind: 'login' | 'logout';
  outcome: 'success' | 'failure';
  occurred_at: string;
}

export interface AuthActivityAiRequest {
  status: 'completed' | 'failed';
  module_key: string | null;
  occurred_at: string;
}

export interface AuthActivityModule {
  key: string;
  label: string;
}

export interface AuthActivityResponse {
  identity: AuthActivityIdentity;
  active_sessions: AuthActivitySession[];
  auth_events: AuthActivityEvent[];
  ai_requests: AuthActivityAiRequest[];
  accessible_modules: AuthActivityModule[];
}

export interface AdminOverviewWindowCount {
  current: number;
  prior: number;
  delta: number;
}

export interface AdminOverviewModuleRef {
  key: string;
  label: string;
}

export interface AdminOverviewResponse {
  generated_at: string;
  anchor: string;
  users: {
    total: number;
    active: number;
    inactive: number;
    roles: { admin: number; user: number; pending: number };
    created: AdminOverviewWindowCount;
  };
  logins: {
    success: AdminOverviewWindowCount;
    failure: AdminOverviewWindowCount;
    logout: AdminOverviewWindowCount;
  };
  ai: {
    total: AdminOverviewWindowCount;
    failure: AdminOverviewWindowCount;
  };
  sessions: {
    active_session_count: number;
    active_user_count: number;
    active_count: number;
  };
  modules: {
    total: number;
    buckets: {
      unavailable: AdminOverviewModuleRef[];
      coming: AdminOverviewModuleRef[];
      development: AdminOverviewModuleRef[];
      active: AdminOverviewModuleRef[];
    };
  };
  system: {
    app_version: string;
    app_env: string;
    database_kind: string;
    newsletter_count: number;
    asset_health: { ok: number; missing: number; checksum_mismatch: number; misconfig: number };
    read_summary: { rows: number; total_reads: number };
  };
  recent_audit: Array<{
    id: number;
    action: string;
    target_type: string | null;
    status: string;
    created_at: string;
  }>;
}

export interface ServiceModule {
  id: number;
  key: string;
  title: string;
  description?: string | null;
  href: string;
  section: string;
  status: 'active' | 'development' | 'coming_soon' | 'hidden' | string;
  badge: string;
  sort_order: number;
  is_enabled: boolean;
  is_external: boolean;
  // Reserved external launcher dispatch. 'none' = not a reserved launcher (legacy/manual
  // is_external usage); 'open_notebook'/'open_webui' are fixed same-host co-deploy ports the
  // frontend resolves itself — never a persisted/arbitrary href. Non-nullable, DB default 'none'.
  launcher_kind: 'none' | 'open_notebook' | 'open_webui';
  visibility: 'public' | 'admin' | string;
  required_permission?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
}


// office-tools(보고서/차트/다이어그램) 공통 뼈대 타입. 각 도구의 요청/응답 타입
// (보고서 생성, 차트 spec/echarts option, 다이어그램 mermaid 등)은 다음 단계에서 추가한다.
export interface OfficeToolCapabilities {
  services: { report: boolean; chart: boolean; diagram: boolean };
  llm: { active: boolean; default_model: string | null; fallback: string };
  limits: Record<string, number>;
}

export interface OfficeJobArtifact {
  filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  download_url: string;
}

export interface OfficeJob {
  job_id: string;
  service: string;
  owner_id: number;
  status: 'running' | 'completed' | 'failed' | string;
  created_at: string;
  updated_at: string;
  warnings: string[];
  artifacts: OfficeJobArtifact[];
  error?: string | null;
}
export interface OfficeJobListItem {
  job_id: string;
  service: string;
  status: 'running' | 'completed' | 'failed' | string;
  created_at: string;
  updated_at: string;
  warnings: string[];
  artifacts: OfficeJobArtifact[];
  title: string | null;
  llm_used: boolean | null;
}

export interface OfficeJobUsage {
  job_count: number;
  total_bytes: number;
  max_jobs_per_owner: number;
  max_bytes_per_owner: number;
}

export interface OfficeJobListResponse {
  jobs: OfficeJobListItem[];
  usage: OfficeJobUsage;
}

export interface OfficeJobDetail {
  job_id: string;
  service: string;
  owner_id: number;
  status: 'running' | 'completed' | 'failed' | string;
  created_at: string;
  updated_at: string;
  request_summary: Record<string, unknown>;
  warnings: string[];
  artifacts: OfficeJobArtifact[];
  error: string | null;
}

export interface ConnectedSession {
  user_id: number;
  username: string;
  last_seen_at: string;
}

export interface LoginEvent {
  id: number;
  user_id?: number | null;
  username: string;
  ip_address?: string | null;
  user_agent?: string | null;
  status: 'success' | 'failure' | 'logout';
  created_at: string;
}

export interface ConnectedUsersResponse {
  active_sessions: ConnectedSession[];
  active_session_count: number;
  active_user_count: number;
  active_count: number;
  recent_login_events: LoginEvent[];
  login_failure_count: number;
  read_tracking_summary: Record<string, number>;
}

export interface SessionPurgeResponse {
  login_events_deleted: number;
  session_activity_deleted: number;
}
export interface AuditEvent {
  id: number;
  actor_username?: string | null;
  actor_role?: string | null;
  action: string;
  target_type: string;
  target_id?: string | null;
  method?: string | null;
  path?: string | null;
  status: string;
  ip_address?: string | null;
  created_at: string;
}

export interface AdminUser {
  id: number;
  username: string;
  display_name?: string | null;
  email?: string | null;
  role: string;
  is_active: boolean;
  permissions: string[];
}

export interface Permission {
  key: string;
}

export interface AdminGroup {
  id: number;
  key: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  permissions: string[];
}


export interface ResourceGrant {
  id: number;
  subject_type: 'user' | 'group';
  subject_id: number;
  resource_type: string;
  resource_id: string;
  permission_key: string;
  created_at?: string | null;
}

export interface RbacGroupPermissionSource {
  group: string;
  key: string;
}

export interface RbacEffectivePermissionSource {
  key: string;
  sources: string[];
}

export interface RbacResourceGrantSource {
  resource_type: string;
  resource_id: string;
  permission_key: string;
  source: string;
}

export interface RbacMatrixUser {
  user_id: number;
  username: string;
  role: string;
  role_permissions: string[];
  direct_permissions: string[];
  group_permissions: RbacGroupPermissionSource[];
  effective_permissions: RbacEffectivePermissionSource[];
  resource_grants: RbacResourceGrantSource[];
}

export interface AiAdminStatus {
  status: Record<string, unknown>;
  request_logs_total: number;
  request_failures: number;
}

export type AssetHealthStatus = 'ok' | 'missing' | 'checksum_mismatch' | 'misconfig';

export interface AssetHealthItem {
  newsletter_id: number;
  newsletter_title: string;
  asset_type: string;
  file_path: string;
  exists: boolean;
  file_size?: number | null;
  checksum?: string | null;
  expected_checksum?: string | null;
  ok: boolean;
  status: AssetHealthStatus;
  resolved_root?: string | null;
  resolved_path?: string | null;
  root_kind: string;
  remediation: string;
  error_code?: string | null;
}

export interface AssetHealthResponse {
  ok: number;
  missing: number;
  checksum_mismatch: number;
  misconfig: number;
  items: AssetHealthItem[];
}

export interface ConfigHealthItem {
  kind: string;
  resolved_path: string;
  exists: boolean;
  readable: boolean;
}

export interface ConfigHealthResponse {
  roots: ConfigHealthItem[];
}

export interface BackupRecord {
  id: number;
  filename: string;
  sha256: string;
  file_size: number;
  status: string;
  created_at: string;
}

export interface BackupRestoreDryRun {
  filename: string;
  valid: boolean;
  compatible: boolean;
  issues: string[];
  would_restore: string[];
  manifest?: Record<string, unknown> | null;
}

export interface UnifiedSearchResult {
  source: string;
  title: string;
  snippet: string;
  url: string;
  score: number;
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

export interface RecentReadItem {
  slug: string;
  title: string;
  last_seen_at: string;
}

export interface RecentReadsResponse {
  items: RecentReadItem[];
}

export interface DocumentListItem {
  // _database/document 기준 상대 경로(.html), 표시 이름(stem), 부모 폴더("" = 루트).
  path: string;
  name: string;
  folder: string;
}

export interface CollectionSearchResult {
  collection: 'document' | 'civil' | 'nsa';
  path: string;
  name: string;
  folder: string;
  snippet: string;
  navigation_url: string;
  score: number;
}

export interface CollectionSearchResponse {
  results: CollectionSearchResult[];
  degraded: boolean;
  reason?: string;
  collections: Array<'document' | 'civil' | 'nsa'>;
}

export interface AiChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface AiAttachment {
  name: string;
  content: string;
}

export interface AiCitation extends CollectionSearchResult {}

export interface AiStatusResponse {
  enabled: boolean;
  base_url: string;
  model: string;
  reachable: boolean;
  model_available: boolean;
  status: 'ok' | 'disabled' | 'unavailable' | 'model_missing';
  detail?: string | null;
}

export interface AiChatResponse {
  model: string;
  message: AiChatMessage;
  citations: AiCitation[];
  conversation_id?: number | null;
  persisted?: boolean;
}

export interface AiConversationSummary {
  id: number;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface AiMessageOut {
  id: number;
  role: string;
  content: string;
  seq: number;
  created_at: string;
  citations: AiCitation[];
}

export interface AiConversationDetail extends AiConversationSummary {
  messages: AiMessageOut[];
}

export interface AiConversationListResponse {
  conversations: AiConversationSummary[];
}

// LLM 연결 레지스트리 (산출물 A). 백엔드는 평문 키를 절대 반환하지 않고 마스킹 값만 준다.
export interface LlmConnection {
  id: number;
  name: string;
  base_url: string;
  default_model?: string | null;
  is_enabled: boolean;
  is_default: boolean;
  verify_tls: boolean;
  api_key_masked: string;
  created_at: string;
  updated_at: string;
}

export interface LlmVerifyResponse {
  ok: boolean;
  models: string[];
  detail?: string | null;
}

// 생성 요청 본문. api_key 는 옵션(무키 Ollama 등)이며 저장 후에는 마스킹 값만 노출된다.
export interface LlmConnectionCreatePayload {
  name: string;
  base_url: string;
  api_key?: string;
  default_model?: string | null;
  is_enabled?: boolean;
  is_default?: boolean;
  verify_tls?: boolean;
}

// 수정 요청 본문. 전 필드 선택적이며, api_key 를 생략하면 기존 키를 유지한다.
export interface LlmConnectionUpdatePayload {
  name?: string;
  base_url?: string;
  api_key?: string;
  default_model?: string | null;
  is_enabled?: boolean;
  is_default?: boolean;
  verify_tls?: boolean;
}

// office-tools 다이어그램 스튜디오(svc03). 서버는 Mermaid 소스만 만들고 브라우저가 렌더한다.
export type DiagramType = 'flowchart' | 'sequence' | 'state' | 'gantt';

// office-tools 샘플 예제 — 각 스튜디오 '예제 불러오기'가 받는 내용 + 폼 프리필 힌트.
export interface OfficeSample {
  key: string;
  tool: 'report' | 'chart' | 'diagram';
  filename: string;
  media_type: string;
  title: string;
  description: string;
  content: string;
  hints: Record<string, unknown>;
}

// Leantime 동거 스택의 실시간 감지 결과. HTTP 헬스 체크 + 앱 식별 결과를 담는다.
// status='ready' 이면서 app_identified=true 일 때만 '열기'가 실제로 동작한다.
export interface LeantimeHealth {
  status: 'ready' | 'unhealthy' | 'starting' | 'absent' | 'error';
  probe_host: string;
  port: number;
  probe_target: string;
  launch_url: string;
  checked_at: string;
  latency_ms: number | null;
  detail: string;
  app_identified: boolean;
}


// 외부 런처(Open Notebook/OpenWebUI) 동거 스택의 실시간 감지 결과. 신원 마커는 요구하지
// 않는다 — HTTP 응답만 오면 status='ready'.
export interface LauncherHealth {
  status: 'ready' | 'starting' | 'absent' | 'error';
  port: number;
  probe_target: string;
  checked_at: string;
  latency_ms: number | null;
  detail: string;
}


// Leantime 읽기 전용 대시보드 DTO — 백엔드가 leantime.read 권한 하에 프로젝트/담당 작업/
// 기간 일정을 그대로 넘겨준다. degraded=true 일 때 reason 으로 사유를 구분한다.
export interface LeantimeProject {
  id: string;
  name: string;
  state: string | null;
  client_name: string | null;
}

export interface LeantimeTask {
  id: string;
  project_id: string | null;
  headline: string;
  status: string | null;
  date_to_finish: string | null;
}

export interface LeantimeCalendarEntry {
  id: string;
  name: string;
  date_start: string | null;
  date_end: string | null;
}

export interface LeantimeReadResponse<T> {
  items: T[];
  degraded: boolean;
  reason: string | null;
  source: string;
  fetched_at: string;
}

export interface DiagramGenerateRequest {
  description: string;
  diagram_type: DiagramType;
  title?: string;
  ai_assist: boolean;
}

export interface OfficeArtifact {
  filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  download_url: string;
}

export interface DiagramGenerateResponse {
  job_id: string;
  status: string;
  title: string;
  diagram_type: DiagramType;
  mermaid: string;
  warnings: string[];
  artifacts: OfficeArtifact[];
  preview_url: string;
  bundle_url: string;
  llm_used: boolean;
}

// office-tools 보고서 스튜디오(svc01). 서버가 Markdown 을 sanitize HTML 로 변환한다.
export type ReportAiMode = 'none' | 'polish' | 'executive';

export interface ReportGenerateResponse {
  job_id: string;
  status: string;
  title: string;
  ai_mode: ReportAiMode;
  llm_used: boolean;
  html: string;
  warnings: string[];
  artifacts: OfficeArtifact[];
  preview_url: string;
  bundle_url: string;
}

// office-tools 차트 스튜디오(svc02). 서버가 pandas 로 집계해 ECharts option(JSON)만 만들고
// 브라우저가 렌더한다. 서버 SVG/PNG 는 없다.
export type ChartType = 'bar' | 'line' | 'area' | 'scatter' | 'pie' | 'histogram';
export type ChartAggregation = 'none' | 'sum' | 'mean' | 'count' | 'min' | 'max';
export type ChartSortMode = 'none' | 'x_asc' | 'x_desc' | 'value_asc' | 'value_desc';
export type ChartOrientation = 'vertical' | 'horizontal';

export interface ChartManualSpecInput {
  type?: ChartType;
  title?: string;
  x: string | null;
  y: string[];
  group?: string | null;
  stacked?: boolean;
  aggregation?: ChartAggregation;
  sort?: ChartSortMode;
  limit?: number;
  orientation?: ChartOrientation;
  x_label?: string | null;
  y_label?: string | null;
}

export interface ChartColumnProfile {
  name: string;
  dtype: string;
  non_null: number;
  null: number;
  unique: number;
  numeric: boolean;
  datetime: boolean;
}

export interface ChartInspectResponse {
  row_count: number;
  column_count: number;
  columns: ChartColumnProfile[];
  sample: Record<string, unknown>[];
}

export interface ChartGenerateResponse {
  job_id: string;
  status: string;
  title: string;
  llm_used: boolean;
  chart_spec: Record<string, unknown>;
  echarts_option: Record<string, unknown>;
  warnings: string[];
  artifacts: OfficeArtifact[];
  preview_url: string;
  bundle_url: string;
}
