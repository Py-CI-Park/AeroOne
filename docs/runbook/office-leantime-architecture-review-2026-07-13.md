# Office Studio·Leantime 통합 아키텍처 시점 평가

- 평가일: 2026-07-13
- 기준: `feature/dashboard-enhancements` 작업트리의 소스와 테스트 소스
- 성격: **시점 평가**. 배포 승인·실환경 검증·법률 자문을 대신하지 않는다.
- 릴리즈 경계: Office Studio와 Leantime 동거는 이 feature branch의 미릴리즈 표면이다. main 병합과 새 오프라인 패키지 검증 전에는 기준선 릴리즈 기능으로 취급하지 않는다.

> 라이선스 판단은 기술적 위험 검토다. Leantime 실행물·수정본을 배포하거나 네트워크로 제공하기 전에는 사내 오픈소스 준수 담당자의 확인이 필요하다.

---

## 1. 평가 결론

| 질문 | 2026-07-13 평가 |
|---|---|
| Office Studio를 현재 Office blocker 때문에 보류해야 하는가 | **코드 품질 gate는 해소됐다.** credential 검색 0건, G008 backend 432건·최종 Office auth 39건·frontend 집중 23건과 typecheck/build, parser·lifecycle·docs/frontend cleaner가 clean이다. 다만 G002 사용자 흐름과 G007 전체 패키지·실환경 검증 전에는 feature branch를 릴리즈 완료로 분류하지 않는다. |
| Office Studio의 현재 진입점은 무엇인가 | 개발중 섹션의 관리자 전용 단일 `Office Studio` 카드(`office-tools`) → 내부 `/office-tools` 허브다. 보고서·차트·다이어그램은 허브 탭과 직접 딥링크로 제공된다. |
| Leantime 동거가 readiness 완료 상태인가 | 아니다. 내부 `/leantime` 안내 카드와 선택적 런처 훅은 있지만, health는 TCP connect만 확인하고 launcher의 상태·종료 코드 계약도 readiness를 증명하지 않는다. |
| Leantime을 AeroOne 코드·DB에 직접 병합해야 하는가 | 아니다. PHP/MariaDB/Leantime 세션·DB·라이선스 경계는 독립 서비스로 유지한다. |
| 일정 데이터 통합이 현재 구현됐는가 | 아니다. FastAPI JSON-RPC Adapter, 일정 요약, 사용자 매핑, SSO는 현재 Office·Leantime 동거 표면에 포함되지 않는다. 이를 구현됐다고 광고해서는 안 된다. |

Office와 Leantime co-deploy 준비도는 별개다. Office G001/G008 보안·lifecycle 코드 gate는 현재 evidence로 해소됐지만, Leantime readiness/launcher와 Office G002 사용자 흐름, G007 오프라인 패키지·실환경 검증은 각각 별도 완료 조건이다.

---

## 2. 현재 구현 사실

### 2.1 Office Studio

| 영역 | 현재 사실 | 진실 원천 |
|---|---|---|
| 대시보드 | 단일 `office-tools` 카드가 `/office-tools` 허브를 연다. `office-report`/`office-chart`/`office-diagram`은 초기 migration의 역사적 행이며 `0012`가 제거한다. | `backend/alembic/versions/20260712_0012_office_tools_single_card.py`, `backend/app/modules/admin/api.py`, `frontend/app/page.tsx` |
| 권한 | 모든 Office API는 로그인과 정확한 `office.use`를 요구한다. 카드 `visibility`는 API 권한을 대신하지 않는다. | `backend/app/modules/office_tools/api/router.py` |
| mutation 보안 | 보고서·차트·다이어그램 생성, inspect, job 삭제와 관리 lifecycle mutation은 CSRF를 검증한다. | `backend/app/modules/office_tools/api/` |
| AI | 활성 OpenAI-호환 연결을 사용하되 미구성·실패 시 모든 도구가 warning과 함께 `rule-based` 폴백으로 계속 동작한다. | `backend/app/modules/office_tools/core/llm_bridge.py`, `docs/runbook/office-tools.md` |
| 입력 경계 | raw multipart/전송량 예산은 413, 파싱 후 의미·ZIP·decompressed/embedded 예산 위반은 422다. | `backend/app/modules/office_tools/upload_limits.py`, `api/reports.py`, `api/charts.py` |
| 산출물 수명주기 | `owner_id` 격리, 30일·사용자별 job/byte·디스크 여유 기본값, read lease, 관리자 purge/recovery/quarantine/evidence 운영 표면과 감사 결과를 제공한다. | `backend/app/modules/office_tools/core/job_store.py`, `api/jobs.py` |
| 카드 migration | Alembic head는 `20260712_0014`: `0012` 단일 허브, `0013` Office Studio 제목, `0014` Leantime 내부 안내 카드다. Frontend fallback ID는 Office `11`, Leantime `12`다. | `backend/alembic/versions/20260712_0012_*`~`0014_*`, `frontend/app/page.tsx` |

### 2.2 Leantime co-deploy

| 영역 | 현재 사실 | 진실 원천 |
|---|---|---|
| 대시보드 | `leantime` 카드는 외부 `8081` 링크가 아니라 내부 `/leantime` 안내 페이지를 연다. | `20260712_0014_leantime_internal_landing.py`, `frontend/app/page.tsx` |
| 상태 확인 | `GET /api/v1/leantime/health`는 `AEROONE_LEANTIME_HEALTH_URL`의 host:port로 TCP connect만 시도하고 `up`/`down`을 반환한다. HTTP 상태·응답 본문·Leantime 기능은 검증하지 않는다. | `backend/app/modules/leantime/service.py` |
| 열기 URL | 브라우저가 현재 protocol·hostname과 health 응답 port를 조합해 새 탭 URL을 만든다. health target의 host/path/scheme를 canonical launch URL로 사용하지 않는다. | `frontend/components/office-tools/leantime-launch.tsx` |
| launcher | `run_all.bat`은 런처가 있으면 호출하고 실패를 경고로 남긴 채 AeroOne을 계속 기동한다. 얇은 래퍼는 launcher 부재와 PowerShell 실패에서도 `exit /b 0`으로 끝난다. | `scripts/run_all.bat`, `scripts/leantime/start-leantime.bat` |
| 경계 | AeroOne은 Leantime DB·세션·프로젝트 데이터를 읽거나 쓰지 않는다. | `backend/app/modules/leantime/`, `docs/runbook/leantime-codeploy.md` |

---

## 3. remediation matrix

### 3.1 검증된 Office 개선

`해결`은 코드·대응 테스트·현재 review evidence가 모두 존재한다는 뜻이다. 이는 해당 코드 gate의 해소를 뜻하며, G002 사용자 흐름이나 G007 패키지·실환경 배포 적합성까지 대신 주장하지 않는다.

| 이전 blocker | 상태 | 현재 구현과 evidence |
|---|---|---|
| 카드 노출만으로 Office API가 열릴 수 있음 | **해결** | 상위 router가 로그인 + `office.use`를 강제한다. `test_office_tools_auth.py`와 `test_office_tools_jobs.py`가 권한 경계를 다룬다. |
| 생성·inspect·lifecycle mutation의 CSRF 누락 | **해결** | 각 mutation에 `require_csrf`를 적용했다. auth/jobs/report/chart/diagram API 테스트가 403 경계를 다룬다. |
| 대용량 multipart가 form parsing 전에 무제한 수용될 수 있음 | **해결** | 경로별 ingress middleware가 declared/chunked 전체·파일·개수 한계를 413으로 차단한다. `test_multipart_ingress_enforces_exact_and_chunked_file_and_total_limits`, `test_multipart_ingress_fast_rejects_content_length_and_many_tiny_files`가 계약을 명시한다. |
| 보고서 자산 ZIP의 요청 공유 예산·canonical 이름·중앙 디렉터리·반복 이미지 경계 부족 | **해결** | compressed/decompressed/member/name/embedded 예산과 ZIP preflight·canonical registry를 적용했다. `test_generate_route_applies_compressed_budget_across_zip_parts_with_413`, `test_generate_route_rejects_duplicate_canonical_key_across_zip_parts_with_422`, `test_unpack_asset_zip_rejects_central_directory_amplification`, `test_unpack_asset_zip_rejects_double_encoded_traversal`, `test_embed_markdown_images_caches_repeated_image_and_enforces_budgets`가 대응한다. |
| owner 산출물의 무기한·비결정적 lifecycle | **해결** | owner quota, 보존, 단일 `/jobs/admin/purge`, recovery/quarantine/evidence inventory, read lease, 감사 receipt와 exact phase-1 replay를 구현했다. Windows directory fsync 미지원은 `platform_best_effort`·비재시도로 공개하며 실제 fsync 오류는 `pending`·재시도로 보존한다. lifecycle·권한 회귀와 cleaner가 clean이다. |
| 대시보드에 Office 카드 3장과 Leantime 외부 dead link를 광고 | **해결** | 단일 Office Studio 허브와 내부 `/leantime` 안내 카드가 최종 migration·코드 seed·fallback에 일치한다. `frontend/tests/app/home-page.test.tsx`가 카드 계약을 다룬다. |

### 3.2 아직 유효한 Leantime readiness/launcher blockers

| blocker | 상태 | 필요한 완료 증거 |
|---|---|---|
| TCP connect를 Leantime readiness로 간주 | **미해결** | 제한 시간 HTTP readiness가 실제 Leantime 응답을 구분해야 한다. 포트 점유·HTTP 500·timeout·정상 응답을 구별하는 테스트와 실환경 관측이 필요하다. |
| health target과 브라우저 launch URL이 한 계약이 아님 | **미해결** | backend 설정과 health 응답이 canonical `launch_url`을 제공하고, loopback/LAN/원격/HTTPS 조합에서 같은 대상이 열리는 증거가 필요하다. |
| 런처의 absent/start-failed/ready 상태와 종료 코드가 구별되지 않음 | **미해결** | launcher가 상태별 결과와 non-zero failure를 보존하고, `run_all.bat`이 선택적 동거를 유지하면서도 이를 명확히 보고하는 batch 검증이 필요하다. |
| IIS/PHP/MariaDB 설치·기동과 AGPL source offer·백업/복구·방화벽이 실제 PC에서 미검증 | **미해결** | 폐쇄망 Windows에서 설치, 재기동, `8081` 접속, `3307` local-only, source offer 접근, backup/restore drill을 기록해야 한다. |

이 표의 Leantime 항목은 Office Studio를 다시 보류시키는 항목이 아니라, Leantime을 “운영 준비 완료”라고 표시하기 전에 충족해야 하는 독립 조건이다.

---

## 4. 기술·라이선스 경계

1. Leantime PHP 코어와 MariaDB를 FastAPI/SQLAlchemy 모델로 직접 읽거나 쓰지 않는다.
2. AeroOne 세션 쿠키를 Leantime 쿠키로 변환하지 않고, Leantime API 키를 브라우저·로그·감사 metadata에 노출하지 않는다.
3. Leantime을 포함하거나 수정 배포할 때는 고정 릴리스의 라이선스·NOTICE·대응 소스와 수정 diff를 AeroOne 코드와 분리해 제공한다.
4. 일정 요약이 필요할 때는 서버 전용 FastAPI Adapter가 JSON-RPC를 읽기 전용으로 호출하는 경계를 검증한다. 현재 이 Adapter는 구현되지 않았다.
5. iframe DOM 결합, Leantime 코어 fork, 전체 일정관리 재구현은 이 평가의 현재 구현 범위가 아니다.

## 5. 100점 기준 개발 성숙도

점수는 구현량이 아니라 **폐쇄망 운영에서 안전하게 사용할 수 있는가**를 기준으로 산정한다. 테스트 소스 존재만으로 만점을 주지 않으며, 실제 패키지·Windows·Leantime 스택 검증이 없으면 운영 점수를 제한한다.

| 평가 대상 | 점수 | 강점 | 감점 요인 | 90점 이상 조건 |
|---|---:|---|---|---|
| AeroOne 대시보드 기반 | **86/100** | DB 기반 카드, 권한·세션·감사, same-origin 프록시, 반응형 UI와 다크 테마, backend/frontend 자동 테스트 | 일부 운영 카드가 미릴리즈 기능이고 전체 오프라인 ZIP 재검증 전 | 전체 테스트·패키징·실브라우저 검증과 카드별 degraded 상태 통일 |
| Office Studio 기능 | **84/100** | 보고서·차트·다이어그램 생성, strict upload/ZIP 경계, owner 격리, quota·보존·exact recovery·감사 API와 G001/G008 코드 gate 완료 | 작업 이력·재열기·복제 UI, 탭 draft/result 보존, 고급 차트 입력과 export 사용성이 남음 | G002 사용자 흐름·export·이력 완성과 G007 패키지·실브라우저 검증 |
| Leantime 동거 런타임 | **38/100** | 독립 서비스 경계, 내부 안내 페이지, 선택적 launcher와 AeroOne 독립 기동 원칙 | TCP 수준 health, canonical URL·상태 모델·restart/stop 계약 부재, 실제 Windows 스택 미검증 | G003 readiness/launcher 및 G006 오프라인 패키징·백업/복구 drill |
| 일정관리 통합 기능 | **22/100** | iframe·DB 직접 접근을 금지한 경계와 JSON-RPC 방향은 합의됨 | 연결 레지스트리·Adapter·정규화 DTO·일정 요약·사용자 매핑 UI가 아직 없음 | G004 서버 Adapter와 G005 네이티브 대시보드 일정면 완성 |
| Office+Leantime 통합 릴리즈 준비 | **52/100** | Office G001/G008 코드 gate와 frontend/backend 자동 검증, 목표 아키텍처·권한·라이선스 분리 원칙 확보 | G002~G006 구현, 전체 오프라인 ZIP과 실제 Leantime·Windows evidence 미완료 | G002~G007 내구 checkpoint와 최종 성과·미검증 항목 기록 |

## 6. 현재 대시보드 기술 스택

| 계층 | 현재 기술 | 대시보드에서의 역할 | 유지 판단 |
|---|---|---|---|
| Web UI | Next.js **15.2** App Router, React **19**, TypeScript **5.7** | SSR/동적 페이지, same-origin API relay, 관리자·Office·Leantime 화면 | 유지. Leantime PHP UI를 이 계층에 복제하지 않는다. |
| 스타일 | Tailwind CSS **3.4**, 공용 UI primitive·디자인 토큰 | 카드·탭·상태·다크 테마와 접근성 일관성 | 유지. Leantime 요약도 같은 토큰의 네이티브 컴포넌트로 구현한다. |
| 시각화 | ECharts **5.6**, Mermaid **11.16** | Office 차트·다이어그램의 브라우저 렌더 | 유지. 폐쇄망 CDN과 서버 PNG 의존을 추가하지 않는다. |
| API | FastAPI, Pydantic 2, SQLAlchemy 2, Alembic | 현재 권한·감사·Office 작업의 서버 신뢰 경계이며, G004에서 Leantime Adapter를 추가할 예정 | 유지. API key와 향후 Leantime 호출은 이 계층 밖으로 노출하지 않는다. |
| 데이터 | SQLite 기본, PostgreSQL 전환 가능, 로컬 파일 JobStore | 대시보드 설정·사용자·감사와 Office 산출물 저장 | Leantime MariaDB와 분리. 두 DB를 join하거나 직접 공유하지 않는다. |
| 인증 | 서명된 HttpOnly 세션 쿠키, CSRF, RBAC permission | UI/API 접근 통제와 mutation 보호 | 유지. Leantime 쿠키 공유 금지; 공통 IdP가 있을 때만 분리된 SSO를 검토한다. |
| 테스트 | pytest/pytest-asyncio/httpx, Vitest/Testing Library | API·경계값·컴포넌트·same-origin proxy 회귀 | 유지하고 Playwright/실브라우저와 Windows batch 검증을 최종 gate에 추가한다. |
| 운영 | Windows batch, 폐쇄망 ZIP, 선택적 co-deploy | AeroOne·Open Notebook·Leantime 기동과 배포 | Leantime은 고정 upstream 릴리스를 별도 프로세스/데이터로 동거시킨다. |

## 7. Leantime 채택 방식 비교와 권장 작업

| 선택지 | 기능 적합성 | 개발·유지비 | 라이선스·운영 위험 | 판단 |
|---|---|---:|---|---|
| upstream Leantime을 별도 서비스로 패키지에 동거 | Leantime 전체 기능을 그대로 사용 | 중간 | AGPL 대응 소스·NOTICE·SBOM과 PHP/MariaDB 운영 필요 | **권장 기본안** |
| Leantime core/fork를 AeroOne 저장소·DB에 직접 내장 | 단기에는 화면·기능이 많아 보임 | 매우 높음 | 업그레이드 충돌, 세션·DB 결합, 수정 배포 준수 범위 확대 | **비권장** |
| Leantime 전체 기능을 FastAPI/Next.js로 다시 구현 | AeroOne UX에 완전 일치 가능 | 극히 높음 | 프로젝트·작업·일정·권한·알림·보고 전체를 장기 유지해야 함 | **비권장** |
| upstream 동거 + 필요한 읽기 API·요약 UI만 AeroOne 네이티브 구현 | 핵심 일정 가시성과 원본 전체 기능을 함께 제공 | 중간 | API allowlist·키 보관·장애 격리 필요 | **최종 권장안** |

| 우선순위 | 권장 작업 | 완료 기준 |
|---:|---|---|
| 1 | Office G001/G008 보안·수명주기 gate | **코드 검증 완료**: credential 검색 0건, backend 432건·Office auth 39건·frontend 집중 23건, cleaner·최종 review evidence. 내구 checkpoint 후 G002로 진행 |
| 2 | Office G002 사용자 흐름 완성 | stale 결과 방지, 탭 상태·URL·ARIA, 고급 차트, 작업 이력·재열기·복제와 실제 artifact export |
| 3 | Leantime G003 런타임 신뢰성 | HTTP readiness, canonical `launch_url`, 상태·지연·실패 사유, start/stop/restart와 AeroOne 독립성 |
| 4 | Leantime G004 서버 Adapter | 암호화 연결 레지스트리, verify/rotate/delete 감사, allowlist JSON-RPC, project/task/calendar DTO |
| 5 | Leantime G005 대시보드 통합 | 프로젝트·내 작업·기간 일정 요약, freshness/degraded, 권한·부분 실패, 원본 딥링크 |
| 6 | Leantime G006 폐쇄망 운영 | 고정 버전·SHA-256·NOTICE·SBOM·대응 소스, 선택 설치, 백업/복구·방화벽·rollback |
| 7 | G007 통합 검증 | 전체 backend/frontend/batch/browser 테스트와 실제 수행·미검증 evidence 표 |


---

## 8. 운영 문서와 evidence

- [Office Studio 현재 운영 계약](office-tools.md): 권한, 단일 허브, API, 413/422, lifecycle, 테스트 source evidence.
- [Leantime co-deploy 런북](leantime-codeploy.md): 설치, source offer, backup/firewall, 실제 운영자 검증 항목.
- [LLM 연결 런북](llm-connections.md): OpenAI-호환 연결 등록·검증·기본 지정.
- [역사적 MVP 통합 분석](../../AeroOne%20Tool/INTEGRATION_ANALYSIS.md): 2026-07-11/12 분석·완료 스냅샷이며 현재 계약이 아님.

이 평가 문서는 코드와 테스트 **소스**를 대조한 2026-07-13 상태다. 이 문서 정리에서는 테스트·lint·format·build·typecheck·launcher 명령을 실행하지 않았다. 운영 또는 릴리즈 주장에는 별도 실행 기록과 실환경 evidence가 필요하다.
