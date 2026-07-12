# Frontend Shared Contract v1 — ClientSession & Safe API Errors

Status: version 1 (frozen for AeroOne v1.13.0 Wave 1). All Wave 1 tasks (session BFF,
account nav, AI scope flags, login redirect) build against this exact shape. Any breaking
change to field names/semantics requires a version bump and a coordinated update across
all consumers.

## 1. `ClientSession` (frontend/lib/types.ts)

```ts
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
```

- `authenticated`: `true` (backend confirmed identity), `false` (backend returned 401),
  `null` (backend unreachable — identity is *not* asserted either way).
- `is_admin`, `can_view_document`, `can_view_nsa`, `can_use_ai` are **derived, server-computed
  flags**. UI components consume these flags only and MUST NOT recompute visibility from
  `permissions`/`resources` themselves — the BFF route is the single derivation authority.

## 2. Derivation authority: `GET /api/frontend/session`

Route: `frontend/app/api/frontend/session/route.ts`.

- Uses `getServerApiBase()` only (no hardcoded loopback fallback — a misconfigured
  `SERVER_API_BASE_URL` must surface as a real failure, not silently mask itself).
- Forwards only the incoming `cookie` header, `cache: 'no-store'`, 5s
  (`AbortSignal.timeout(5000)`) per upstream call.
- Calls (all cookie-forwarded so the backend filters per caller):
  1. `GET {base}/api/v1/auth/me` — identity/role.
  2. `GET {base}/api/v1/auth/effective-permissions` — `{ permissions: string[], resources: ClientSessionResourceGrant[] }`.
  3. `GET {base}/api/v1/admin/service-modules/public` — array of `{ key, is_enabled, ... }`.
- Every response (200/401/unreachable) sets `Cache-Control: no-store`.

### Derivation rules

| Flag | Rule |
| --- | --- |
| `is_admin` | `role === 'admin'` |
| module "available" | a module with matching `key` is present in the public modules list **and** `is_enabled !== false` |
| `can_view_document` | module `document` available; **defaults to `true`** if the service-modules fetch fails (Document stays public on BFF failure) |
| `can_view_nsa` | `authenticated === true` AND module `nsa` available AND (`is_admin` OR `permissions` includes `collections.nsa.read` or `search.nsa.read` OR a resource grant with `resource_type === 'collection' && resource_id === 'nsa'`) |
| `can_use_ai` | `authenticated === true` AND module `ai` available |

### Response matrix

| Scenario | `authenticated` | `is_admin` | `can_view_document` | `can_view_nsa` | `can_use_ai` |
| --- | --- | --- | --- | --- | --- |
| `/auth/me` unreachable (network error/timeout) | `null` | `false` | `true` | `false` | `false` |
| `/auth/me` → 401 | `false` | `false` | `true` | `false` | `false` |
| Authenticated non-admin, no nsa grant | `true` | `false` | depends on module | `false` | depends on module |
| Authenticated non-admin, resource grant `collection/nsa` | `true` | `false` | … | `true` (if nsa module enabled) | … |
| Authenticated non-admin, global permission `collections.nsa.read` or `search.nsa.read` | `true` | `false` | … | `true` (if nsa module enabled) | … |
| Authenticated admin | `true` | `true` | … | `true` (if nsa module enabled) | `true` (if ai module enabled) |
| Module `nsa`/`ai` disabled (`is_enabled: false`) | `true` | any | … | `false` | `false` |
| `/service-modules/public` fetch fails | `true` | any | `true` (default) | `false` | `false` |

## 3. Safe API errors (`frontend/lib/api.ts`)

`ApiError extends Error` carries a numeric `status` and a message from
`getSafeApiErrorMessage(status)` — exported so UI components reuse the same mapping instead
of re-deriving Korean copy. Raw backend response bodies are **never** placed into the
`Error`/`ApiError` message for `browserFetch` or `fetchClientSession`.

```ts
export function getSafeApiErrorMessage(status: number): string {
  if (status === 401) return '로그인이 필요합니다';
  if (status === 403) return '접근 권한이 없습니다';
  if (status === 422) return '요청 형식이 올바르지 않습니다';
  if (status === 429) return '요청이 너무 잦습니다';
  if (status >= 500) return '서버 오류가 발생했습니다';
  return '요청 처리에 실패했습니다';
}
```

| Status | Korean message |
| --- | --- |
| 401 | 로그인이 필요합니다 |
| 403 | 접근 권한이 없습니다 |
| 422 | 요청 형식이 올바르지 않습니다 |
| 429 | 요청이 너무 잦습니다 |
| 5xx | 서버 오류가 발생했습니다 |
| other | 요청 처리에 실패했습니다 |

`browserFetch<T>` and `fetchClientSession` both throw
`new ApiError(getSafeApiErrorMessage(response.status), response.status)` on non-OK responses,
never `response.text()`.

## 4. Fixture examples

Anonymous (401 from `/auth/me`):

```json
{
  "authenticated": false,
  "username": null,
  "role": null,
  "is_admin": false,
  "can_view_document": true,
  "can_view_nsa": false,
  "can_use_ai": false,
  "permissions": [],
  "resources": []
}
```

Backend unreachable:

```json
{
  "authenticated": null,
  "username": null,
  "role": null,
  "is_admin": false,
  "can_view_document": true,
  "can_view_nsa": false,
  "can_use_ai": false,
  "permissions": [],
  "resources": []
}
```

Authenticated admin, all modules enabled:

```json
{
  "authenticated": true,
  "username": "root",
  "role": "admin",
  "is_admin": true,
  "can_view_document": true,
  "can_view_nsa": true,
  "can_use_ai": true,
  "permissions": [],
  "resources": []
}
```

Authenticated non-admin with an NSA resource grant, ai module disabled:

```json
{
  "authenticated": true,
  "username": "analyst",
  "role": "user",
  "is_admin": false,
  "can_view_document": true,
  "can_view_nsa": true,
  "can_use_ai": false,
  "permissions": [],
  "resources": [
    { "resource_type": "collection", "resource_id": "nsa", "permission_key": "collections.nsa.read" }
  ]
}
```

Safe error example (raw backend body never surfaces):

```ts
// Upstream 500 with body "internal stack trace leak: /etc/secrets"
// -> ApiError { status: 500, message: '서버 오류가 발생했습니다' }
```

## 5. Known non-goal follow-ups (owned by other Wave 1 tasks)

The following consumers still reference the pre-contract shape (`session.isAdmin`) and are
explicitly out of scope for this task; they are owned by the account-nav, AI-scope-flags, and
login-redirect tasks respectively:

- `frontend/app/page.tsx` (`resolveIsAdmin`)
- `frontend/components/ai/ai-chat-workspace.tsx`
- `frontend/components/layout/admin-nav-link.tsx`
- `frontend/tests/app/home-page.test.tsx`
- `frontend/tests/components/admin-nav-link.test.tsx`
- `frontend/tests/components/ai-scope.test.tsx`
