# 단계 10 — IP 기반 읽음추적(열람 횟수) 모듈

- 분류: minor (`1.1.0`) — 신규 모듈 추가 (AGENTS.md §9.6)
- dev 브랜치: `1.1.0-dev`
- 기능 commit: `2ec9016`

---

## 1. 의도 (왜 만들었는가)

관리자가 "누가(어느 접속 IP 가) 어떤 글을 몇 번 읽었는지" 확인할 수단이 없었다. 폐쇄망 LAN 에선 책상 PC 마다 IP 가 고정에 가까워 **접속 IP 를 식별자**로 쓰기로 운영자가 결정했고, 다음 3가지를 합의했다.

- **1차 목표 = 열람 "횟수"** (이름 매핑·정식 로그인은 후속)
- **투명성 = 조용히 기록, 관리자만 열람** (독자 고지 없음)
- **보존 = 무기한, 수동 purge 만** (자동 만료 없음)

IP 는 개인정보로 분류될 수 있어 조용한 수집의 사내 정책·PIPA 리스크를 고지받은 뒤 운영자가 그대로 선택한 결정이며, 그 근거를 `docs/CLOSED_NETWORK_GUIDE.md` §11.6 과 `docs/runbook/read-tracking.md` 에 남겼다.

## 2. 핵심 설계 결정 (아키텍처 급소)

모든 뉴스레터 읽기 경로가 **SSR loopback fetch** 라, 백엔드 `request.client.host` 가 독자 브라우저가 아니라 Next 서버(127.0.0.1)로 퇴화한다. 따라서 독자 실 IP 를 얻는 유일한 경로는 **브라우저가 백엔드를 직접 호출하는 body 없는 read-beacon** 이다.

- `POST /api/v1/newsletters/{id}/read` — body 없음·무인증·무CSRF, `request.client.host` 기록. body 가 없어 `sendBeacon` 의 text/plain ↔ FastAPI JSON 파싱 충돌(422)을 회피한다.
- LAN 모드에서만 실 IP 가 잡히고, `--local`(loopback)이면 전부 `127.0.0.1` 로 퇴화(관리자 화면 배너로 안내).
- 리버스 프록시 없는 직결(`uvicorn --host 0.0.0.0`) 전제. 프록시를 두면 이 전제가 깨지며 XFF 신뢰 정책을 다시 세워야 한다.

## 3. 구현 (무엇을 바꿨는가)

- **신규 모듈** `backend/app/modules/read_tracking/` — newsletter 5-디렉토리 컨벤션 복제.
  - `newsletter_read_events`: `(newsletter_id, client_ip)` UniqueConstraint upsert + **30분 디바운스** → `read_count` = "30분 이상 간격 열람 세션 수". `newsletter_id` FK `ondelete=CASCADE`. 시각은 전적으로 DB `func.now()` 로 채우고 비교만 naive UTC 로 정규화(SQLite tz-naive 함정 회피).
  - 공개 비콘은 존재검증으로 임의 id 행 생성을 막고, 폴더 스캔 부수효과 회피를 위해 `auto_sync` 의존성을 붙이지 않는다.
  - 관리자 조회 `GET /admin/read-events`(`get_current_admin`) + 수동 `POST /admin/read-events/purge`(`get_current_admin` + `require_csrf`).
  - 마이그레이션 `20260603_0002` (`down_revision=20260327_0001`), `alembic/env.py` 모델 import, `main.py` 라우터 등록.
- **프런트엔드** — `read-beacon.tsx`(sessionStorage 세션내 1회 가드) 를 읽기 뷰에 마운트, `/admin/read-events` 관리자 화면(글별 집계·IP 행·loopback 배너·전체삭제 CSRF), 대시보드 비활성 카드 href 정직화(`'#'`).
- **문서** — 신규 `docs/runbook/read-tracking.md`, `docs/INDEX.md`(§2/§6/§7), `docs/CLOSED_NETWORK_GUIDE.md` §11.6.

## 4. 검토하고 제외한 대안

- **Next 프록시 XFF 주입** — XFF 위조 가능 + SSR 경로상 독자 IP 부재로 제외.
- **ip_label(IP→이름) / 정식 로그인** — 1차 목표(횟수)와 무관, 폐쇄망 계정 관리 부담으로 후속.
- **보존 자동 만료** — 운영자가 무기한·수동을 택해 제외, 메커니즘(purge)만 제공.

## 5. 검증

- backend `python -m pytest tests` — **96 passed** (기존 83 + 신규 13, 실패 0).
- frontend `npm run test`(Vitest) — **77 passed** (기존 71 + 신규 6, 30 파일). `tsc --noEmit` exit 0.
- `alembic upgrade head` — `newsletter_read_events` + 인덱스 2 + unique 생성, head=`20260603_0002`.
- architect THOROUGH 검증 APPROVE (CRITICAL·HIGH 0).

## 6. 코드 / 회귀 방지

| 영역 | 위치 |
|---|---|
| 모델 / 디바운스 upsert | `backend/app/modules/read_tracking/models/read_event.py`, `repositories/read_event_repository.py` |
| 비콘 / 관리자 조회·purge | `backend/app/modules/read_tracking/api/public.py`, `api/admin.py` |
| 프런트 비콘 / 관리자 화면 | `frontend/components/newsletter/read-beacon.tsx`, `frontend/app/admin/read-events/page.tsx` |
| 회귀 방지 | `backend/tests/unit/read_tracking/` (6), `backend/tests/integration/test_read_tracking_api.py` (7), `frontend/tests/components/read-beacon.test.tsx` (2), `read-events-list.test.tsx` (3), `frontend/tests/lib/record-read.test.ts` (1) |
