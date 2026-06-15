# 폐쇄망 오픈소스 도입 프로세스 (재사용 플레이북)

이 문서는 **외부 오픈소스를 AeroOne 폐쇄망 환경에 안전하게 도입하는 재사용 가능한 표준 프로세스**입니다. Open Notebook(NotebookLM 대안) 도입에서 검증된 패턴을 일반화했습니다. 새 오픈소스를 도입할 때 이 순서를 그대로 따르면 같은 품질로 적용할 수 있습니다.

- 적용 사례(완결): Open Notebook → [`docs/runbook/open-notebook-airgap.md`](runbook/open-notebook-airgap.md), 설치 매뉴얼 [`docs/runbook/closed-network-install-manual.md`](runbook/closed-network-install-manual.md), 계획 `.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`.

---

## 0. 원칙 (불변)

1. **병합 아닌 동거(co-deploy).** 외부 앱을 AeroOne 코어에 병합하지 않는다. 별도 프로세스 군으로 나란히 띄우고 결합점을 최소화한다(보통 둘 — 대시보드 진입 링크 + 공유 추론 엔드포인트).
2. **AeroOne 회귀 불변.** backend pytest / frontend vitest / `AGENTS.md §6 위험신호` 를 절대 건드리지 않는다. 변경은 가산적(additive)만.
3. **폐쇄망 자기완결.** 도입 앱은 자체 런타임·의존성·prebuilt 산출물을 동봉한 airgap 번들로 만든다. 폐쇄망 PC는 인터넷·사전 설치가 필요 없어야 한다(공유 추론 엔진은 예외).
4. **무인 자동 설정.** 운영자는 배치 2~3개만 실행. 환경변수(IP/CORS/키)·모델/서비스 등록은 설치/기동 스크립트가 자동 처리한다.
5. **upstream 추적 보존.** 코어는 수정하지 않고, AeroOne 고유 패치(airgap 도구·thin adapter)는 별도 fork 브랜치에만 둔다. 'core diff 0' 를 기계적으로 검증한다.

---

## 1. 도입 결정 (3택 1 + ADR)

| 옵션 | 내용 | 채택 기준 |
|---|---|---|
| **A. co-deploy (권장)** | vendoring + 나란히 배치, 결합점 최소 | upstream이 활발/대형, 라이선스 허용(MIT/Apache 등), 재구현 비용 큼 |
| B. 재구현 | 핵심 기능만 AeroOne 네이티브로 | 기능이 작고 upstream 추적 불필요할 때만 |
| C. 코드 병합(subtree 흡수) | — | 거의 비권장 (upstream 이력 혼입, 핀 충돌, 코어 경계 붕괴) |

산출물: 라이선스 확인(MIT/Apache/BSD 등 재배포 가능 여부) + ADR(결정/드라이버/대안/귀결). 합의가 필요하면 `/skill:ralplan` 으로 consensus plan 부터.

---

## 2. Vendoring — submodule + rebasing fork 브랜치

- `vendor/<app>` 으로 git submodule. 핀 대상은 pristine upstream tag 가 아니라 **AeroOne 유지 fork 브랜치**(`<app>/airgap`) = upstream tag 위에 airgap 도구 + adapter 만 rebase.
- **adapter 경로 동결**: airgap 번들 도구 + thin adapter(런처/설정)만 fork에 추가. 경로 목록을 런북에 동결한다.
- **core diff 0 게이트**: `git -C vendor/<app> diff --quiet <tag>..HEAD -- . ":(exclude)<adapter경로>"` 의 exit-code(=`--exit-code`, `--stat` 아님)로 코어 무수정을 기계 검증. 사례 스크립트: [`scripts/check_open_notebook_core_diff.cmd`](../scripts/check_open_notebook_core_diff.cmd).
- (운영자 게이트) fork 브랜치 생성 + GitHub push + `.gitmodules` 연결.

---

## 3. Airgap 번들 (자기완결)

인터넷 PC 빌드 스크립트(`<app>/airgap/1-online-package.bat` 패턴)가 다음을 하나의 폴더+ZIP으로 묶는다:
- 앱 소스(빌드 산출물 제외) + **자체 런타임**(예: 포터블 Python/uv/Node) + **의존성 캐시**(오프라인 재설치용) + **prebuilt frontend** + 인코딩/모델 등 런타임 캐시.
- 설치/기동/정지 배치(`2-airgap-install` / `3-run` / `stop`) + 자동 프로비저닝 스크립트 동봉.

검증된 사실: `uv sync --frozen --offline` 로 네트워크 차단 상태에서 venv 전체 재구성 가능, prebuilt `.next` + `node_modules` 동봉으로 폐쇄망에서 빌드 불필요.

---

## 4. 무인 자동 프로비저닝 (핵심)

배치만으로 "전기능 동작"하려면 다음을 스크립트가 자동 처리한다:

| 자동화 | 방법 | 사례 |
|---|---|---|
| 환경변수 `.env` | 설치 스크립트가 생성 — 랜덤 시크릿, 추론 엔드포인트, **CORS 오리진(LAN IP 자동조합)** | `write_env.ps1` + `detect_lan_ip.ps1` |
| 모델/서비스 등록 | 기동 후 health 확인 → 앱 API로 모델 등록·기본 할당(멱등) | `provision_models.ps1` (POST `/api/models` + PUT `/api/models/defaults`) |
| 공유 추론 모델 | 인터넷 PC pull → blob 단방향 반입 → 폐쇄망 Ollama 적재 | `gemma4:12b` + `nomic-embed-text` |

**되짚을 함정 3가지 (사례에서 실제로 발견):**
1. **CORS + credentials**: 프론트가 다른 포트의 API를 직접 호출하면 CORS. `allow_credentials=True` 는 와일드카드 `*` 와 호환되지 않으므로 **명시 오리진**(`CORS_ORIGINS`) 자동 기입 필수.
2. **환경변수 누출**: 동거한 AeroOne이 `CORS_ORIGINS`/`OLLAMA_BASE_URL` 등을 OS env로 누출하면 `uv --env-file` 가 이를 덮어쓰지 못한다. 기동 스크립트가 해당 OS env를 **비워(.env 우선)** 방어.
3. **추론 엔드포인트 호스트**: 같은 PC면 `127.0.0.1`(기본 바인딩과 호환). 원격 추론 PC면 그 PC가 `0.0.0.0` 바인딩이어야 하고 `--host` 인자로 명시.

---

## 5. Co-deploy 통합 (AeroOne 측, 가산만)

- **대시보드 링크**: `frontend/app/page.tsx` MODULES 에 external 카드 1개(동적 `http://<host>:<port>` — client 컴포넌트 `window.location.hostname`). `ServiceCard` external 분기(`target=_blank rel="noopener noreferrer"`). 동반 vitest.
- **공유 추론**: 같은 Ollama 엔드포인트 재사용. 동시성 예산(RAM/`OLLAMA_*`/staggered/ health 임계/degraded mode)을 문서화.
- **DB·세션·포트 분리**: 절대 공유하지 않음. 포트 비충돌 확인(preflight).
- **통합 런처**: `scripts/run_all.bat` — staggered(AeroOne health 후 외부앱) + 부재 시 단독 폴백. `scripts/stop_all.bat`.

---

## 6. 폐쇄망 패키징 (분리 번들)

- 두 산출물 **각자 빌드/반입**: AeroOne ZIP + 외부앱 airgap ZIP. AeroOne ZIP 은 vendored 트리 미포함(`offline_package.bat` `/XD vendor` 가산 — `AGENTS.md §6` 보호목록은 무변경, 추가만).
- 운영자 반입물 목록을 설치 매뉴얼에 명시(보통 2 ZIP + 공유 추론 엔진 설치파일 + 모델 blob).

---

## 7. 검증 게이트 (도입 완료 기준)

1. AeroOne 회귀 불변: backend pytest / frontend vitest / `tsc` / `next build` 그대로.
2. `AGENTS.md §6` 위험신호 무변경(자체점검).
3. core diff 0 == 0 (vendoring 시).
4. **클린 배치-온리 재현**: 데이터/`.env` 지운 fresh 상태에서 설치 배치 → 기동 배치만으로 전기능 동작(모델 자동 할당·UI 렌더·CORS 정상)을 실증.
5. 폐쇄망 e2e 스모크(운영자 게이트): 인터넷 PC 빌드 → 단방향 반입 → 설치 → 기동 → 4프로세스 health + 통합 링크 도달.
6. broken-link 0 + 문서(README/매뉴얼/런북/INDEX) 동시 갱신.

---

## 8. upstream 동기화 (반복 가능, 코어 보존)

`fetch upstream tag → fork 브랜치 rebase(airgap/adapter 보존, bare checkout 금지) → core diff 0 게이트 → airgap 번들 재빌드(lockfile/cache 재시드) → 스모크+회귀 통과 전 핀 미승격 → 한국어 커밋으로 핀 승급`. 상세: [`docs/runbook/open-notebook-airgap.md`](runbook/open-notebook-airgap.md) §4.

---

## 9. 다음 도입용 체크리스트

- [ ] 라이선스 재배포 가능 확인 + ADR 작성(co-deploy 채택?).
- [ ] `vendor/<app>` submodule + `<app>/airgap` fork 브랜치 + core-diff-0 게이트.
- [ ] airgap 번들 스크립트(자체 런타임·캐시·prebuilt 동봉) + 자동 `.env`/모델/서비스 프로비저닝 + env-leak 방어 + CORS 명시 오리진.
- [ ] AeroOne 대시보드 external 카드(+vitest) + 공유 추론 예산 문서 + `run_all`/`stop_all`.
- [ ] `offline_package.bat /XD <vendor>` 가산(§6 무변경).
- [ ] 클린 배치-온리 재현 검증 + 회귀 불변 + 운영자 게이트(빌드/push/airgap 스모크) 명시.
- [ ] README·설치 매뉴얼·런북·INDEX·AGENTS 동시 갱신.
