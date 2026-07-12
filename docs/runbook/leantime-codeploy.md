# Leantime 동거(co-deploy) 운영 런북

> Leantime 은 AeroOne 에 **흡수하지 않고 '동거(co-deploy)'** 한다. AeroOne 은 대시보드에 외부
> 링크 카드 한 장과 선택적 기동 훅만 제공하고, 실제 앱(PHP + MariaDB + IIS)은 운영자가 별도로
> 설치·기동한다. 이 문서는 그 경계와 설치 절차, 라이선스 의무, 검증 체크리스트를 정리한다.
>
> ⚠ **이 저장소 환경에서는 IIS/PHP/MariaDB 실제 설치·기동을 검증할 수 없다.** 아래 절차의
> 서비스명·AppPool 명·경로·포트는 운영자가 실 배포 PC 에서 실측해 확정해야 한다(각 항목에
> "운영자 검증 필요" 로 표시).

---

## 1. 두 스택의 경계 (가장 중요)

AeroOne 과 Leantime 은 **코드/DB/세션/포트가 완전히 분리된 두 개의 독립 스택**이다. 통합은
아래 두 자리로만 이뤄지며, 코드 병합은 하지 않는다.

| 통합 자리 | 내용 |
|---|---|
| 대시보드 카드 → 내부 안내 페이지 | `service_modules` 의 `leantime` 행(`is_external=false`, `href=/leantime`). 클릭 시 AeroOne 안의 `/leantime` 안내 페이지로 이동한다(외부 링크가 아니라 내부 라우트라 미설치 상태에서도 빈 화면이 뜨지 않는다). |
| 실시간 기동 감지 (health) | `/leantime` 페이지가 백엔드 `GET /api/v1/leantime/health` 를 호출해 `127.0.0.1:8081` 로 TCP 프로브한다. `up` 이면 '구동 중' 배지 + '열기' 버튼 활성, `down` 이면 '미설치·미구동' 배지 + 설치 절차 안내. '열기' 는 **구동 중일 때만** Leantime(8081)을 새 탭으로 연다. |
| 선택적 기동 훅 | `scripts/run_all.bat` 이 AeroOne 안정화 후 Leantime 런처를 **있으면 위임 호출, 없으면 경고 후 진행**. |

- AeroOne 백엔드는 Leantime 을 **감지(TCP 프로브)만** 한다 — DB 스키마/인증/데이터에는 접근하지 않는다.
  감지 대상 host:port 는 환경변수 `AEROONE_LEANTIME_HEALTH_URL` (기본 `http://127.0.0.1:8081`) 로 재정의한다.
- Leantime 데이터(프로젝트/이슈)는 Leantime 의 MariaDB 에만 있고 AeroOne 은 접근하지 않는다.
- 카드·안내 페이지는 **관리자 전용**(`visibility='admin'`) 이라 비관리자 대시보드에는 노출되지 않는다.
- 진실 원천: 백엔드 `app/modules/leantime/{service,api}.py`, 프런트 `app/leantime/page.tsx` +
  `components/office-tools/leantime-status.tsx`.

---

## 2. 포트 배정

| 서비스 | 기본 포트 | 비고 |
|---|---|---|
| AeroOne backend (uvicorn) | 18437 | 고정. Leantime 과 충돌 금지 |
| AeroOne frontend (Next) | 29501 | 고정 |
| Leantime (IIS 웹사이트) | **8081** | 링크 카드 href 기본값 |
| Leantime MariaDB | **3307** | AeroOne 은 사용하지 않음. 기본 MySQL 3306 과 분리 |

- **피해야 할 포트**: 8000 / 8001 / 8502 / 5055 / 8088 / 11434 / 18437 / 29501 은 AeroOne·Open
  Notebook·Ollama 가 이미 쓴다. Leantime/MariaDB 는 8081 / 3307 로 고정해 충돌을 피한다.
- 카드 href 를 8081 이외로 바꾸려면 §6 을 따른다.

---

## 3. 오프라인 설치 절차 (운영자, Administrator 권한)

Leantime 완제품 설치는 SaaS Kit(`AeroOne Tool/saas-kit-v2.0.0/`)의 complete-stack 번들을 참조한다.
아래는 요약이며, 상세는 SaaS Kit 의 `aeroone-tool/docs/COMPLETE_STACK_RUNBOOK.md` 와
`scripts/Install-Offline.ps1` / `Start-All.ps1` 을 따른다.

### 3.1 인터넷 스테이징 PC (반입물 준비)

```bat
:: SaaS Kit 루트에서
00_BUILD_COMPLETE_OFFLINE_BUNDLE.bat
05_VERIFY_COMPLETE_OFFLINE_BUNDLE.bat
```

- 산출물 1: Leantime / PHP(FastCGI) / MariaDB / IIS 선행조건 (`bundle/`).
- SHA-256 manifest 를 보존한 채 승인된 매체 절차로 폐쇄망에 반입한다. **(운영자 검증 필요)**

### 3.2 폐쇄망 워크스테이션 (설치·기동)

```bat
:: Administrator 로
05_VERIFY_COMPLETE_OFFLINE_BUNDLE.bat
10_INSTALL_COMPLETE_STACK.bat     :: IIS 기능·PHP FastCGI·MariaDB(3307)·Leantime 사이트(8081) 설치
20_START_COMPLETE_STACK.bat       :: MariaDB 서비스 + W3SVC + AppPool + Website start → AeroOne 순
22_STATUS_COMPLETE_STACK.bat      :: 상태 확인
```

설치가 구성하는 것 **(각 항목 운영자 검증 필요)**:

- IIS 웹 서버 역할 + PHP FastCGI 핸들러.
- MariaDB 서비스(포트 3307) + Leantime 스키마/DB 계정.
- Leantime 애플리케이션을 IIS AppPool + Website 로 등록, 포트 8081 바인딩.
- Leantime 최초 관리자 계정/조직 초기 설정(브라우저 최초 접속 시).

### 3.3 AeroOne 기동 훅 연결

AeroOne 런처(`scripts/run_all.bat`)가 Leantime 을 선택적으로 함께 띄우게 하려면 환경변수로
Leantime 런처를 가리킨다.

```bat
:: Leantime 런처 위치를 지정(기본값은 ..\Leantime\start-leantime.bat)
set "AEROONE_LEANTIME_LAUNCHER=C:\AeroOneSuite\start-leantime.bat"

:: 또는 AeroOne 이 동봉한 얇은 래퍼를 쓰고, 그 래퍼가 SaaS Kit 스크립트를 가리키게 함
set "AEROONE_LEANTIME_LAUNCHER=%CD%\scripts\leantime\start-leantime.bat"
set "AEROONE_LEANTIME_SCRIPTS=C:\AeroOneSuite\scripts"   :: Start-All.ps1 이 있는 폴더

run_all.bat
```

- 런처가 존재하면 `run_all.bat` 이 AeroOne backend health 확인 후 위임 호출한다.
- 런처가 없으면 `[RUN-ALL][INFO ] Leantime launcher not found ... operator install required` 를
  출력하고 AeroOne 만 진행한다(동거는 **선택적**, Leantime 부재가 AeroOne 기동을 막지 않는다).
- 계획만 확인하려면 `run_all.bat --dry-run` 으로 Leantime 훅 분기를 미리 볼 수 있다.
- AeroOne 이 동봉한 래퍼: [`scripts/leantime/start-leantime.bat`](../../scripts/leantime/start-leantime.bat)
  — `AEROONE_LEANTIME_SCRIPTS` 아래 `Start-All.ps1`(IIS/MariaDB start)을 위임 호출하는 얇은
  참조 배치. 실제 서비스명/AppPool 명은 **운영자 검증 필요**.

---

## 4. AGPL v3 라이선스 의무 (반드시 준수)

Leantime 은 **GNU AGPL v3** 로 배포된다. AGPL 은 "네트워크를 통해 사용자와 상호작용하는
소프트웨어"에 대해 **대응 소스(corresponding source) 제공 의무**를 부과한다.

- 사내 사용자가 브라우저로 Leantime(8081) 에 접속하는 것은 AGPL 의 "네트워크 상호작용"에
  해당한다 → **수정 여부와 무관하게** 실행 중인 정확한 버전의 대응 소스를 사용자가 받을 수 있게
  해야 한다.
- Leantime 을 **수정**했다면(테마·플러그인·코어 패치 등) 그 수정 소스까지 포함해 제공한다.
- 실무 조치 **(운영자 검증 필요)**:
  - [ ] 실행 중 Leantime 버전과 정확히 일치하는 소스 트리 사본을 사내에서 접근 가능한 위치
        (예: 사내 파일서버 `\\fileserver\oss\leantime\<version>-source`)에 게시한다.
  - [ ] Leantime UI 또는 사내 포털에 "소스 코드 받기(source offer)" 링크/안내를 노출한다.
  - [ ] 수정본이 있으면 diff/patch 를 소스 트리와 함께 보관한다.
- AeroOne 자체는 Leantime 과 **링크(외부 URL)와 프로세스 위임**으로만 연결되며 코드/DB 를
  공유하지 않으므로, AeroOne 소스가 AGPL 로 전염되지는 않는다. 다만 **Leantime 배포·운영 주체가
  AGPL 소스오퍼 의무의 당사자**임을 문서로 남긴다.
- 참고: SaaS Kit `aeroone-tool/docs/SECURITY_LICENSE.md` 의 라이선스 경계 절.

---

## 5. 백업 / 방화벽 / 자동 시작

**(전 항목 운영자 검증 필요)**

- **백업**: Leantime 데이터는 AeroOne 백업 대상이 아니다(정책상 공개/정적 루트만 백업). Leantime
  의 MariaDB 덤프 + 업로드 폴더를 SaaS Kit `30_BACKUP_COMPLETE_STACK.bat` 로 별도 백업하고,
  접근 통제된 NAS 로 복사한 뒤 **복구 리허설**을 수행한다.
- **방화벽**: 다른 PC 에서 Leantime 에 접속하려면 8081 인바운드를 LAN 범위로만 연다. AeroOne 의
  `scripts/allow_lan_firewall.cmd`(18437/29501 전용)와 별개로 Leantime 규칙을 추가한다. MariaDB
  3307 은 워크스테이션 외부로 절대 열지 않는다(로컬 전용).
- **자동 시작**: IIS AppPool/Website 와 MariaDB 서비스는 Windows 서비스로 자동 시작되도록 구성한다
  (SaaS Kit `Register-AeroOneAutostart.ps1` 계열 참조). AeroOne 과 순서 의존이 없으므로 각자
  독립적으로 부팅 시 기동해도 무방하다.
- **HTTPS**: 기본 트래픽은 HTTP 다. 민감정보 전송 전 승인된 사내 리버스 프록시 + 인증서를 적용한다.

---

## 6. Leantime 포트를 8081 이외로 바꾸기

대시보드 카드는 이제 **내부 안내 페이지(`/leantime`)** 로 가고, 실제 Leantime 열기/감지는 그
페이지가 담당한다. 운영자 환경의 포트/호스트가 다르면 **DB 카드 링크가 아니라** 감지·열기
기준을 바꾼다.

- **감지 대상(host:port)**: 환경변수 `AEROONE_LEANTIME_HEALTH_URL` 로 지정한다(예:
  `set AEROONE_LEANTIME_HEALTH_URL=http://127.0.0.1:9090`). 백엔드가 이 대상으로 TCP 프로브해
  '구동 중/미구동'을 판정한다. 미설정 시 킷 기본값 `http://127.0.0.1:8081`.
- **열기 포트**: `/leantime` 페이지의 '열기' 버튼은 health 응답의 `port` 로 접속 호스트 기준
  URL(`{protocol}//{hostname}:{port}`)을 만든다(LAN 접속 대응). health 대상 포트를 바꾸면 열기
  포트도 함께 따라간다.
- 카드 자체(`service_modules.leantime`)의 진실 원천 3자리(마이그레이션 `20260712_0014`,
  `admin/api.py` `DEFAULT_SERVICE_MODULES`, `frontend/app/page.tsx` `FALLBACK_MODULES`)는
  `href=/leantime, is_external=false` 로 일치한다 — 코드 기본값은 건드리지 않는다.

---

## 7. 운영자 검증 체크리스트

배포 PC 에서 아래를 직접 확인해야 "Leantime 동거 완료" 로 볼 수 있다.

- [ ] IIS / PHP(FastCGI) / MariaDB(3307) 실제 설치·기동 확인 (`22_STATUS_COMPLETE_STACK.bat`).
- [ ] Leantime 8081 바인딩 및 브라우저 접속(최초 관리자 설정 완료) 확인.
- [ ] AeroOne 대시보드의 Leantime 카드 → `/leantime` 안내 페이지 이동 확인(관리자 로그인 상태).
- [ ] `/leantime` 페이지 상태 배지: Leantime 기동 시 '구동 중' + '열기' 활성, 미기동 시 '미설치·미구동'
      확인(`GET /api/v1/leantime/health` 가 up/down 을 정확히 반영하는지).
- [ ] '열기' 버튼이 구동 중일 때 8081 을 새 탭으로 여는지 확인(미구동 시 비활성 안내인지).
- [ ] 비관리자 계정 대시보드에는 Leantime 카드가 **노출되지 않음** 확인.
- [ ] AGPL 대응 소스오퍼(수정본 포함) 게시 위치 확보 및 접근 링크 노출 확인.
- [ ] `run_all.bat` 에서 `AEROONE_LEANTIME_LAUNCHER` 훅 동작 확인(런처 존재 시 위임 기동,
      부재 시 경고 후 AeroOne 진행).
- [ ] Leantime MariaDB 덤프/업로드 백업 + 복구 리허설 1회 수행.
- [ ] 방화벽: 8081 은 LAN 범위로만, 3307 은 로컬 전용 확인.

---

## 관련 문서

- SaaS Kit complete-stack 런북: `AeroOne Tool/saas-kit-v2.0.0/aeroone-tool/docs/COMPLETE_STACK_RUNBOOK.md`
- SaaS Kit 라이선스 경계: `AeroOne Tool/saas-kit-v2.0.0/aeroone-tool/docs/SECURITY_LICENSE.md`
- AeroOne 폐쇄망 종합 가이드: [`../CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md)
- Open Notebook 동거(같은 co-deploy 패턴 선례): [`open-notebook-airgap.md`](open-notebook-airgap.md)
- AeroOne 측 얇은 래퍼: [`../../scripts/leantime/start-leantime.bat`](../../scripts/leantime/start-leantime.bat)
