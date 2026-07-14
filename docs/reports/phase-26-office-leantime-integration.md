# 단계 26 — Office Studio 보안·수명주기 강화 + Leantime 동거 통합 최종 검증 및 성과 보고

## 변경 배경

이 단계는 durable Ultragoal 플랜(7 목표 + G001 architect 차단으로 추가된 G008)의 최종 검증·성과 보고입니다. 두 축을 다뤘습니다.

- **Office Studio(svc01~03)**: 공용 초기 비밀번호 노출 제거, 모든 생성 mutation 의 CSRF·permission·retired-credential 정책, OfficeJobStore 의 보존기간·quota·디스크 임계치·owner 삭제·감사 가능한 관리자 purge·격리·복구·내구 receipt, 그리고 stale 결과 제거·경합 방지·`llm_used` provenance·고급 차트 입력·작업 이력/재열기/설정복제·검증 가능한 다운로드.
- **Leantime 동거(co-deploy)**: TCP-only 감지를 제한시간 HTTP readiness + 앱 식별(5 상태)로 교체, 서버측 암호화 연결 레지스트리 + allowlist JSON-RPC 읽기 어댑터, 네이티브 대시보드 통합면, 그리고 고정 버전·SHA-256 매니페스트·NOTICE/SBOM·선택적 수명주기(설치·기동·중지·재시작·상태·백업·복구·방화벽·rollback)·OIDC/LDAP 분리 세션 절차.

Leantime 은 AeroOne 에 **흡수하지 않고 별도 스택으로 동거**하며, 통합은 공식 JSON-RPC/health/OIDC·LDAP 경계로만 이뤄집니다(소스/DB/세션/쿠키 병합 없음). AeroOne 은 Leantime 실패와 **독립적으로** 계속 동작합니다.

## 목표별 완료 증거

| 목표 | 내용 | 상태 | 핵심 증거 |
|---|---|---|---|
| G001 | Office 보안·산출물 수명주기 강화 | ✅ (G008 로 해소) | architect 11 차단 → G008 에서 전부 해소 후 supersede |
| G008 | G001 architect 차단 최종 해소 | ✅ 완료 | backend 432, Office auth 39, 프런트 proxy 23; cleaner 0 blocker; architect CLEAR/APPROVE; QA red-team passed |
| G002 | Office 고급 사용자 흐름 | ✅ 완료 | URL 동기 ARIA 탭·탭별 상태 보존·경합 안전·`llm_used` provenance·고급 차트(x/y/group/집계/누적)·이력/재열기/설정복제·안전 다운로드; 프런트 63·백엔드 diagram 17·jobs 183; architect CLEAR/APPROVE; QA passed |
| G003 | Leantime 상태·Windows 수명주기 | ✅ 완료 | HTTP readiness+앱식별 5상태(absent/starting/unhealthy/ready/error), canonical launch_url·latency·detail, /health 항상 200, start/stop/restart/status+run_all readiness, AeroOne 독립; backend 16·batch 36·프런트 7; architect CLEAR/APPROVE(2차) |
| G004 | 서버 연결 레지스트리 + JSON-RPC 어댑터 | ✅ 완료 | base_url+scoped key 암호화 저장(평문 노출 0, x-api-key 헤더 전용), 관리자 verify/회전/삭제/감사, allowlist JSON-RPC·제한시간·오류 매핑·정규화 DTO, projects/tasks/calendar 읽기(항상 200 degraded), Leantime DB 미접근; backend 71+15; architect CLEAR/APPROVE(2차) |
| G005 | 대시보드 일정관리 통합면 | ✅ 완료 | same-origin 프록시 위 네이티브 UI·자원별 freshness/degraded·403/401 개별 처리·LAN-safe 딥링크·iframe/스크래핑 없음·디자인토큰/접근성; 프런트 23; architect CLEAR/APPROVE |
| G006 | 오프라인 패키징·운영 준수 | ✅ 완료 | 고정 버전(3.5.13)+SHA-256 매니페스트+NOTICE/SBOM+policy(무수정·no patch), verify-bundle(ok/mismatch/missing/placeholder/malformed→0/2/1), backup/restore/rollback/firewall, OIDC/LDAP 분리 세션 런북(쿠키 공유 금지); batch 37; architect CLEAR/APPROVE |
| G007 | 최종 통합 검증·성과 보고 | ✅ 본 문서 | 아래 검증 결과표 |

## 검증 결과 (전체 통합, 본 단계 실측)

| 검증 스위트 | 결과 | 아티팩트 |
|---|---|---|
| backend integration (A) | **101 passed** | `g007-integration-a-junit.xml` |
| backend integration (B) | **101 passed** | `g007-integration-b-junit.xml` |
| backend unit core(비-Office) | **128 passed** | `g007-unit-core-junit.xml` |
| backend Office parser(chart/report/diagram) | **154 passed** | `g007-office-parser-junit.xml` |
| backend Office jobs+auth | **183 passed** | `g007-office-jobs-junit.xml` |
| backend Leantime(health/conn/adapter/admin) | **71 passed** | `g004-backend-junit.xml` |
| backend Windows batch(run_all dry-run 포함) | **37 passed** | `g006-batch-junit.xml` |
| frontend Vitest 전체 | **430 passed / 80 files** | — |
| frontend typecheck (`tsc --noEmit`) | 성공 | — |
| frontend production build (`next build`) | 컴파일 성공, 전 라우트 emit | — |
| Windows batch dry-run(run_all/start/status/verify-bundle) | 통과 | batch 스위트 내 |
| alembic 마이그레이션 체인(→ `20260714_0016`) | upgrade/downgrade/upgrade 통과 | — |
| 문서 상대 링크(변경 4 문서) | 108 링크 0 broken | — |

- 백엔드 합계(파티션 합, 중복 없음): **775 passed / 0 failed** (integration 202 · unit core 128 · Office 337 · Leantime 71 · batch 37). 프런트엔드 **430 passed / 0 failed** (82 파일).
- 스토리별 architect 3레인(아키텍처/제품/코드) 리뷰 + executor QA red-team 모두 CLEAR/APPROVE 또는 passed. G003·G004 는 각 1회 반복(WATCH/REQUEST_CHANGES → 수정 → 재검토 CLEAR/APPROVE).

## API 계약·권한·경계값·실패 모드 검증(요약)

| 표면 | 계약 | 실패 모드 검증 |
|---|---|---|
| Office 생성/수명주기 | office.use 상속, 관리 mutation 은 admin.office.manage+CSRF, retired credential 차단 | 미인증 401·무권한/무CSRF 403(부작용 없음), crash/restart 내구 replay, 교체/스왑 evidence 미해결, ingress 오버플로우 차단 |
| Office 작업 이력 | owner-scoped, 허용목록 표시 필드(title/llm_used)만 | 민감 키 노출 0, 타 소유자 미노출, legacy/running 은 null |
| Leantime health | 항상 200 + 9필드 계약 | 예외 시 status='error'(500 아님), 스킴 http/https 반영 |
| Leantime 읽기 | leantime.read 필요, JSON-RPC allowlist·제한시간 | 미구성/복호화불가/인증실패/업스트림 장애 → 200 degraded, 키 미노출, 500 없음 |
| Leantime 관리 | admin.leantime.read/manage + CSRF, 마스킹 응답 | 무권한/무CSRF 403, verify(ok/auth_failed/unreachable/error) 키 미노출, 모든 mutation 감사 |
| 대시보드 프록시 | same-origin GET 전용, 쿠키/CSRF 중계 | 403/401 자원별 처리, degraded 배너, traversal 차단 |
| 패키징 verify | SHA-256 매니페스트 대조 | ok→0 / mismatch·missing→2 / placeholder→0(WARN) / malformed→1 |

## human_blocked(외부 자원 필요로 본 저장소 환경에서 미검증)

아래는 코드/계약/실패 모드는 mock·단위·계약 수준에서 검증했으나, **실제 외부 스택·자격·권한이 있어야만** 최종 확인 가능한 항목입니다. 운영자 검증이 필요합니다.

| 항목 | 검증된 부분(본 저장소) | human_blocked(운영자 필요) |
|---|---|---|
| Leantime 실제 스택 | run_all/start/stop/restart/status/backup/restore/rollback/firewall 스크립트 문법·로그·종료코드·독립성 | IIS+PHP(FastCGI)+MariaDB 실제 설치·기동·수명주기 동작 |
| Leantime JSON-RPC 라운드트립 | allowlist·제한시간·오류 매핑·DTO 정규화·degraded (mock transport) | 실 Leantime + 실 scoped API key 로 projects/tasks/calendar 실응답 |
| SHA-256 번들 무결성 | verify-bundle 로직(ok/mismatch/missing/placeholder/malformed) | 실제 릴리스 바이너리의 SHA-256 매니페스트 채움 및 대조 |
| OIDC/LDAP 분리 세션 | 분리 세션·role mapping·쿠키 공유 금지 절차 문서 | 공통 IdP 존재 시 실제 로그인/역할/로그아웃 격리 검증 |
| 실 브라우저 E2E | 컴포넌트·프록시·API 계약(Vitest), readiness/일정/Office 생성·다운로드 단위 | 라이브 풀스택 + 실제 브라우저(Playwright)로 화면·다운로드 실행 검증 |

## 후속(handoff)

1. 운영자는 스테이징 PC 에서 `packaging/leantime/leantime-bundle.manifest.json` 의 `<fill-on-staging>` SHA-256 을 실제 릴리스 체크섬으로 채우고 `scripts/leantime/verify-bundle.bat <bundle_dir>` 로 무결성을 확인한다.
2. 폐쇄망 PC 에서 Leantime 스택 설치 후 `scripts/leantime/status-leantime.bat` 로 ready 확인, `/leantime` 대시보드에서 실 데이터 요약과 딥링크를 확인한다.
3. 관리자 API 로 Leantime 연결(base_url+scoped key)을 등록·verify 하고, 대시보드가 실 projects/tasks/calendar 를 표시하는지 확인한다.
4. 공통 IdP 가 있으면 `docs/runbook/leantime-oidc-ldap.md` 절차로 분리 세션·역할 매핑을 적용하고 로그인/로그아웃 격리를 검증한다.
5. 실 브라우저 E2E(Playwright)로 readiness 배지, 일정 요약, Office 보고서/차트/다이어그램 생성·다운로드를 최종 확인한다.

## 진실 원천(빠른 색인)

| 영역 | 코드/문서 위치 |
|---|---|
| Office 보안/수명주기 | `backend/app/modules/office_tools/{api,core,services,schemas}.py` |
| Office 프런트 흐름 | `frontend/components/office-tools/*`, `frontend/lib/{api,types}.ts` |
| Leantime health/readiness | `backend/app/modules/leantime/{service,api}.py`, `frontend/components/office-tools/leantime-status.tsx` |
| Leantime 연결/어댑터 | `backend/app/modules/leantime/{models,schemas,connection_service,rpc_client,read_api,admin_api}.py` |
| Leantime 대시보드 | `frontend/components/office-tools/leantime-dashboard.tsx`, `frontend/app/leantime/page.tsx` |
| Leantime 수명주기 스크립트 | `scripts/leantime/*.bat`, `scripts/run_all.bat` |
| 패키징·운영 준수 | `packaging/leantime/*`, `docs/runbook/leantime-codeploy.md`, `docs/runbook/leantime-oidc-ldap.md` |
