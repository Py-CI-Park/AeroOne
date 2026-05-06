# 기여 가이드

AeroOne 은 폐쇄망 사내 운영을 일차 목적으로 하는 운영 소프트웨어입니다. 외부 사용·재배포는 [`LICENSE`](LICENSE) 의 제약을 따르며, 이 문서는 본 저장소에서 작업할 때 적용되는 **커밋 / PR / 검증 규칙**을 정리합니다.

---

## 1. 작업 전에 읽을 문서

| 분류 | 위치 | 무엇을 위해 |
|---|---|---|
| 운영 매뉴얼 | [`README.md`](README.md) | 시스템 정체성, 빠른 시작, 폐쇄망 흐름 |
| 저장소 규칙 | [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) | 커밋·PR 한국어 규칙 원본 |
| 개발 계획 | [`docs/dev_plan/20260327_newsletter_platform_mvp.md`](docs/dev_plan/20260327_newsletter_platform_mvp.md) | 범위·완료 기준·리스크 |
| 로컬 런북 | [`docs/runbook/local-dev.md`](docs/runbook/local-dev.md) | 개발 환경 구성, worktree 주의 |
| 폐쇄망 런북 | [`docs/runbook/windows-offline.md`](docs/runbook/windows-offline.md) | 오프라인 패키지 / 설치 절차 |
| 인증 정책 | [`docs/runbook/admin-auth.md`](docs/runbook/admin-auth.md) | `/admin/*` 신뢰 경계 |

---

## 2. 커밋 메시지 규칙

### 2.1 형식

- **제목과 본문 모두 한국어**로 작성합니다.
- 제목은 변경의 **의도(왜 이 변경을 하는지)** 를 한 줄로 드러냅니다. 단순한 파일 나열, 영문 한 줄, `fix` / `update` / `cleanup` 같은 모호한 메시지는 허용하지 않습니다.
- 본문은 짧게 끝내지 않고 다음을 한국어 문단 1~3개로 적습니다.
  - 변경 배경
  - 선택한 접근 방식
  - 고려한 제약
  - 제외한 대안과 그 이유
- 마지막에는 Lore protocol trailer 를 한국어 값으로 채웁니다.

### 2.2 Lore Trailer 키

| 키 | 의미 |
|---|---|
| `Constraint:` | 이 변경에서 반드시 지켜야 했던 제약 |
| `Rejected:` | 고려했지만 채택하지 않은 대안 + 그 이유 |
| `Confidence:` | 변경의 자신감 수준 (예: 높음 / 보통 / 낮음) |
| `Scope-risk:` | 영향 범위 위험 (예: 좁음 / 보통 / 넓음) |
| `Directive:` | 후속 작업자가 따라야 할 지침 (필요 시) |
| `Tested:` | 어떤 검증을 수행했는지 |
| `Not-tested:` | 일부러 또는 환경 제약으로 검증하지 못한 부분 |

### 2.3 예시

```text
홈 내비게이션과 미리보기 상단 제어를 정돈한다

홈 화면에서 Newsletter 항목이 두 군데 노출되고 있어 사용자에게 동일한 진입점이
두 번 보이는 문제를 해소한다. 동시에 미리보기 화면 상단 제어가 달력과 형식
선택 사이에서 시각적 우선순위가 흐트러지는 문제를 함께 정리한다.

홈 카드 설명을 제거하고 달력은 기본 접힘 상태로 시작하도록 했으며, Report
format 패널은 달력 접힘 높이에 맞춰 정렬했다. HTML 배지 문구는 사용자가 즉시
판별 가능하도록 줄였다.

Constraint: 병합 커밋도 한국어 제목과 한국어 본문을 사용해야 한다
Rejected: 카드 설명만 유지하고 내비게이션은 그대로 두기 | 동일 진입점 중복이 그대로 남는다
Confidence: 높음
Scope-risk: 좁음
Tested: npm run test, npm run typecheck, npm run build, git diff --check
Not-tested: GitHub Actions 필수 체크가 비어 있어 원격 체크는 실행되지 않았다
```

### 2.4 금지

- 한 줄짜리 영문 커밋
- 제목만 있고 본문이 없는 커밋
- 맥락 없이 `fix`, `update`, `cleanup` 같은 모호한 메시지
- 실제 의도보다 구현 세부만 나열한 메시지
- 시크릿 (`.env`, JWT 키, 관리자 비밀번호 등)을 포함한 커밋

---

## 3. PR 규칙

- 제목과 본문 모두 가능한 한 **한국어**로 작성합니다.
- 본문은 마크다운으로 다음 항목을 포함합니다.
  - **변경 배경**
  - **핵심 수정 사항**
  - **검증 결과** (실행한 명령과 결과)
  - **영향 범위 / 후속 작업**
- 자기 PR 자기 승인은 GitHub 정책 상 제한됩니다. 검증 결과 섹션을 충분히 적어 두면 셀프 머지 시점에 근거가 남습니다.
- 머지 커밋 자체도 한국어 제목 + 한국어 본문 + Lore trailer 를 따릅니다.

---

## 4. 코드 컨벤션 요약

상세는 글로벌 규칙 문서에 위임하지만, 본 저장소에서 자주 부딪히는 항목만 정리합니다.

- **불변성**: 객체 변이 대신 새 객체를 만든다.
- **시크릿 환경 변수화**: 절대 하드코딩하지 않는다. setup 시 랜덤 생성되는 값을 그대로 쓴다.
- **시스템 경계 검증**: 사용자 입력과 외부 데이터는 zod / pydantic 으로 검증한다.
- **작은 파일 / 작은 함수**: 파일 800줄, 함수 50줄, 중첩 4단계 한도. 넘으면 분리한다.
- **TDD**: 신규 기능과 버그 픽스는 실패 테스트 → 최소 구현 → 리팩터링 순서로 진행한다.
- **설계 산출물 동기화**: 새 기능은 가능하면 `docs/superpowers/plans/` 와 `docs/superpowers/specs/` 에 짧은 계획·설계 문서를 함께 추가한다.

---

## 5. 검증 절차 (PR 머지 전 권장)

```bash
# backend
cd backend && . .venv/bin/activate
python -m pytest

# frontend
cd frontend
npm run test
npm run typecheck
npm run build

# 형식 점검
git diff --check
```

Windows 경로 / 폐쇄망 흐름이 영향을 받는 변경이면 다음을 추가로 확인합니다.

```cmd
setup.bat --dry-run
start.bat --dry-run
offline_package.bat --dry-run
setup_offline.bat --dry-run
```

---

## 6. 보안 관련 변경 시 추가 절차

- `auth`, `csrf`, `cookie`, `cors`, `storage` 정적 노출, `_debug.html` 정책에 영향을 주는 변경은 PR 본문에 **위협 모델 변화**를 한 단락으로 적습니다.
- production 기본값 거부 정책(`APP_ENV=production` 환경에서의 secret/admin 비번 검증)을 우회하거나 완화하는 변경은 별도 PR 로 분리합니다.
- 관리자 인증을 `/admin/*` 라우트에서 제거하려면 mutation / sync 가 다른 신뢰 경계 뒤로 이동했다는 근거를 함께 제출해야 합니다 ([`docs/runbook/admin-auth.md`](docs/runbook/admin-auth.md)).

---

## 7. 이슈와 토론

- 외부 사용 / 라이선스 예외 / 보안 신고는 [`LICENSE`](LICENSE) 의 연락처로 직접 연락합니다.
- 그 외 일반 개선 제안은 GitHub Issues 또는 사내 채널을 통해 제출합니다.

---

## 8. 라이선스

기여 시 본인이 작성한 코드와 문서는 [`LICENSE`](LICENSE) 의 조건 아래 본 저장소에 통합되는 것에 동의하는 것으로 간주합니다.
