# 읽음추적 (IP 기반 열람 횟수) 런북

뉴스레터를 **어느 접속 IP 가 몇 번 읽었는지** 기록하고, 관리자만 조회·정리하는 기능의 설계·한계·운영 절차를 정리한다.

- 도입 버전: 1.0.23 (예정)
- 1차 목표: **열람 횟수**(누가=IP, 이름 매핑은 미포함)
- 투명성: **조용히 기록, 관리자만 열람** (독자 고지 배너 없음 — 운영자 결정)
- 보존: **무기한**, 수동 purge 만 제공

---

## 1. 어떻게 IP 를 얻는가 (핵심 설계)

모든 뉴스레터 읽기 경로는 **서버사이드(SSR) loopback fetch** 다 — 브라우저가 Next 서버를 거쳐 백엔드를 호출하므로, 백엔드가 보는 `request.client.host` 는 독자 브라우저가 아니라 **Next 서버(127.0.0.1)** 가 된다.

그래서 독자의 실제 IP 를 얻는 유일한 정직한 경로는 **브라우저가 백엔드를 직접 호출하는 읽음 비콘**이다:

```
독자 브라우저  ──(POST, body 없음)──►  http://<host>:18437/api/v1/newsletters/{id}/read
                                         FastAPI: request.client.host = 독자 LAN IP
```

- LAN 모드(`NEXT_PUBLIC_API_BASE_URL=http://<host>:18437`)에서만 실제 LAN IP 가 잡힌다.
- `--local`(loopback) 모드면 모든 접속이 `127.0.0.1` 로 기록된다 — **오류가 아니라 설계상 퇴화**. 관리자 화면이 "loopback 모드" 배너로 알려준다.
- 비콘은 `navigator.sendBeacon`(body 없음)을 우선 사용해 페이지 이탈에도 전송을 보장하고, 미지원 환경은 `fetch(keepalive)` 로 폴백한다.
- 같은 브라우저 세션·같은 글은 `sessionStorage` 가드로 1회만 발화한다(서버도 30분 디바운스).

## 2. 데이터 모델 / 카운트 규칙

테이블 `newsletter_read_events` — (newsletter_id, client_ip) 1쌍당 1행(UniqueConstraint).

| 컬럼 | 의미 |
|---|---|
| `newsletter_id` | 어떤 글 (FK, 글 삭제 시 CASCADE 로 함께 삭제) |
| `client_ip` | 접속 IP |
| `read_count` | 해당 IP 의 **30분 이상 간격 열람 세션 수** |
| `first_seen_at` / `last_seen_at` | 최초 / 최근 열람 (DB `func.now()` 로만 채움) |

**read_count 동작**: 같은 (글, IP) 재방문이 마지막 기록으로부터 30분 이내면 `read_count` 는 늘지 않고 `last_seen_at` 만 갱신된다. 30분을 넘으면 `read_count` 가 1 증가한다. 즉 read_count 는 "조회수"가 아니라 "열람 세션 수"다.

## 3. 한계 (반드시 인지)

- **IP ≠ 개인.** IP 는 자리/접속점 식별이지 개인 식별이 아니다.
  - **DHCP 표류**: 같은 사람이 날짜에 따라 다른 IP 를 받을 수 있다.
  - **NAT/공유 PC**: 여러 사람이 한 IP 를 공유하면 서로 다른 열람이 1행으로 병합된다. NAT 게이트웨이 단일 IP 환경이면 추적이 사실상 무의미하다.
- **리버스 프록시 없는 직결 전제.** `start_offline.bat` 은 `uvicorn --host 0.0.0.0` 로 프록시 없이 직접 구동하므로 `request.client.host` 가 실 IP 다. 앞단에 프록시를 두게 되면 이 전제가 깨지며, 그때는 신뢰 가능한 `X-Forwarded-For` 처리 정책을 따로 세워야 한다(현재는 XFF 기본 불신).

## 4. 운영 절차

- **조회**: 관리자 로그인 → `/admin/newsletters` 상단 "읽음 현황" 또는 직접 `/admin/read-events`. 글별 총 열람·고유 IP 집계와 IP 별 행을 본다.
- **정리(purge)**: 보존은 무기한이므로 자동 삭제가 없다. 관리자 화면의 "전체 기록 삭제" 버튼(CSRF 보호)으로 수동 정리한다. SQL 직접 정리도 가능:
  ```sql
  DELETE FROM newsletter_read_events;                    -- 전체
  DELETE FROM newsletter_read_events WHERE newsletter_id = ?;  -- 특정 글
  ```
- **백업**: 읽음 기록은 `_database/db/aeroone.db` 안에 있으므로 기존 DB 백업 대상에 자동 포함된다(별도 파일 없음).

## 5. 개인정보(PIPA) 주의

IP + 열람 이력은 개인을 식별할 수 있는 정보로 분류될 수 있고, 고지 없는 수집은 사내 정책·법적 검토 대상이 될 수 있다. 본 기능은 운영자가 "조용히 기록, 관리자만 열람"을 인지하고 선택한 결과다. 운영 시 **사내 고지·보존기간 정책 수립을 권고**한다.

## 6. 코드 진실 원천

| 영역 | 위치 |
|---|---|
| 모델 / 디바운스 upsert | `backend/app/modules/read_tracking/models/read_event.py`, `repositories/read_event_repository.py` (`READ_DEBOUNCE`) |
| 공개 비콘 / 관리자 조회·purge | `backend/app/modules/read_tracking/api/public.py`, `api/admin.py` |
| 라우터 등록 / 마이그레이션 | `backend/app/main.py`, `backend/alembic/versions/20260603_0002_read_events.py`, `backend/alembic/env.py` |
| 프런트 비콘 / 관리자 화면 | `frontend/components/newsletter/read-beacon.tsx`, `frontend/lib/api.ts` (`recordNewsletterRead`), `frontend/app/admin/read-events/page.tsx`, `frontend/components/admin/read-events-list.tsx` |
| 회귀 테스트 | `backend/tests/unit/read_tracking/`, `backend/tests/integration/test_read_tracking_api.py`, `frontend/tests/components/read-beacon.test.tsx`, `read-events-list.test.tsx`, `frontend/tests/lib/record-read.test.ts` |
