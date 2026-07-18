# gongmuwon(공무원) 내장 검토 — 다음 버전 목표

- 상태: **검토(review) 단계 · 구현 미착수** — 다음 버전 목표로 타당성만 정리
- 대상: [`Kminer2053/gongmuwon`](https://github.com/Kminer2053/gongmuwon) — "로컬 AI 에이전트 워크스페이스: 공무원"
- 요청: AeroOne 대시보드에서 Leantime 옆 **새 단추(카드)** 로 gongmuwon 을 AeroOne 의 한 tool 로 내장하는 방안 검토

---

## 1. gongmuwon 이 무엇인가 (실사 근거: 공개 저장소 README/파일 트리)

인터넷 없이 내 PC 안에서 도는 **공무원 업무 AI 워크스페이스**. 대화·지식·문서를 한 화면에서 처리하고 자료가 PC 밖으로 나가지 않는다(폐쇄망 지향). AeroOne 과 목표(폐쇄망 로컬 AI)가 매우 가깝다.

| 항목 | 내용 |
|---|---|
| 배포 형태 | **Tauri 2 데스크톱 앱**(Windows 10/11 x64, WebView2). 브라우저 URL 이 아니라 설치형 `.exe` |
| 프런트 | React 19 (Tauri WebView 안에서 렌더) |
| 백엔드 | **FastAPI (Python 3.11)** — 로컬 프로세스로 AI/지식/문서 API 제공 |
| AI | 로컬 Ollama `gemma-4 E2B`(멀티모달) 동봉. 외부 API 선택 가능 |
| 주요 기능 | 업무대화(근거·출처 인용) · 일정 · **문서작성(HWPX 생성)** · 내 지식폴더(폴더 색인·업무 위키·증분 동기화) · 실행기록 · 환경설정 |
| 데이터 | 전부 로컬. 지식폴더는 지정 폴더를 **그 자리에서** 색인(복사·업로드 없음) |
| 라이선스 | 앱 코드 MIT 표기, 저장소 License 는 "Other"(모델/자산은 별도 조건 가능 — **재배포 전 실검토 필수**) |
| 배포 크기 | 앱만 수십 MB, AI 팩 포함 합계 약 6.3GB(4분할 zip), 설치 약 12GB |

## 2. AeroOne 과의 관계 — 겹침과 차별

- **겹침**: AeroAI(문서 근거 챗), Office Studio(보고서·차트·다이어그램), Document(HTML 보관), Open Notebook(소스 정리) 와 기능이 상당 부분 겹친다.
- **차별(gongmuwon 고유)**: ① **HWPX(한글) 문서 생성** — AeroOne 에 없음. ② **내 지식폴더 in-place 색인 + 업무 위키 자동 구성 + 증분 동기화**. ③ 일정·알림·실행기록이 대화 세션 중심으로 엮인 워크플로.

## 3. 핵심 제약 — Leantime 과 통합 모델이 다르다

Leantime 은 **웹 앱**(php -S 가 `http://localhost:8081` 로 브라우저 접근 가능한 UI 를 서빙)이라, AeroOne 이 "새 탭 링크 + 헬스 프로브" 로 붙일 수 있었다. 반면 **gongmuwon 은 Tauri 데스크톱 앱**이다:

- UI 가 브라우저에서 여는 URL 이 아니라 **WebView2 창**이다 → AeroOne 대시보드 카드가 `http://host:port` 로 "열기" 할 대상이 없다.
- 브라우저(AeroOne 프런트)는 샌드박스라 **로컬 `.exe` 를 직접 실행하지 못한다** → Leantime 처럼 "링크 클릭 → 앱 화면" 이 성립하지 않는다.
- 즉, 현재 형태 그대로는 Leantime 식 co-deploy 링크 카드로 붙일 수 없다.

## 4. 통합 옵션과 평가

| 옵션 | 방식 | 실현성 | 비고 |
|---|---|---|---|
| **A. 데스크톱 런처 카드** | 카드 클릭 시 gongmuwon `.exe` 실행 | 낮음 | 브라우저에서 exe 직접 실행 불가. custom URL protocol(`gongmu://`) 등록 시 가능하나 OS 설정·보안 검토 필요 |
| **B. FastAPI 백엔드 재사용(헤드리스)** | gongmuwon 의 FastAPI 를 헤드리스로 띄우고 AeroOne 이 그 API(지식·HWPX)를 프록시 | **중(가장 유망)** | gongmuwon 백엔드가 고정 포트로 API 를 노출하는지, 인증/CORS 계약이 무엇인지 실검토 필요. AeroOne 은 Leantime 처럼 same-origin 프록시 + 상태 배지로 붙일 수 있음 |
| **C. 기능 이식** | HWPX 생성·지식폴더 색인만 AeroOne 모듈로 재구현/포팅 | 중~높음(공수 큼) | 라이선스(Other) 확인 후 소스 포팅. 폐쇄망 순도·번들 정책과 잘 맞음. 가장 무겁지만 통합도 최고 |
| **D. 안내 카드(문서 링크)** | Leantime 처럼 "별도 설치 안내" 카드만 제공(내장 아님) | 높음 | 가장 저비용. "내장" 요구엔 미달하나 1차 릴리스로 적합 |

## 5. 다음 버전 권고

1. **1차(저비용, 즉시 가능)**: 옵션 **D** — 대시보드 Development 섹션에 gongmuwon **안내 카드**를 추가하고(외부 별도 설치 앱), 설치·연동 가이드를 `docs/runbook/` 에 둔다. Leantime 안내 페이지와 동일 패턴.
2. **2차(내장의 실체, 검증 후)**: 옵션 **B** 실사 — gongmuwon FastAPI 가 안정 포트·문서화된 API(특히 HWPX 생성, 지식폴더 검색)를 헤드리스로 제공하는지 확인. 제공된다면 AeroOne same-origin 프록시(`/api/frontend/gongmuwon/*`) + 상태 배지로 **AeroAI/Office Studio 안에서 HWPX 내보내기·지식 검색을 직접 호출**하는 것이 가장 자연스러운 "내장".
3. **선결 조건(모든 옵션 공통)**:
   - **라이선스 실검토** — 저장소 License 가 "Other". 앱 코드 MIT 여도 동봉 모델(gemma-4)·자산의 재배포 조건을 반드시 확인.
   - **폐쇄망 순도·번들 정책 정합** — AI 팩 6.3GB 는 AeroOne 오프라인 ZIP 정책(대용량 자산 제외)과 충돌. gongmuwon 은 **별도 반입물**로 두고 AeroOne 은 연동만(현 Leantime·Open Notebook·Ollama 모델과 동일 원칙).
   - **중복 기능 정리** — AeroAI/Office Studio/Document 와의 역할 경계를 먼저 정해 UX 중복을 피한다(gongmuwon 은 "HWPX + 지식폴더" 강점만 노출하는 방향 권장).

## 6. 결론

gongmuwon 은 AeroOne 과 철학이 같아 통합 가치가 높다. 다만 **Tauri 데스크톱 앱**이라 Leantime 식 링크 카드로는 바로 붙지 않으므로, 다음 버전에서 **(1) 안내 카드 선반영 → (2) FastAPI 헤드리스 API 재사용(옵션 B) 실사 → (3) HWPX·지식폴더를 AeroOne 안에서 직접 호출**하는 단계적 내장을 권고한다. 착수 전 **라이선스·번들 정책·기능 중복** 3가지를 반드시 선검토한다.
