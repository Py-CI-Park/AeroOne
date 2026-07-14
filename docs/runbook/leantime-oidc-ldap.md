# Leantime OIDC/LDAP 통합 절차 (별도 세션, 선택)

> **이 문서는 공통 사내 IdP(OIDC 제공자 또는 LDAP/Active Directory)가 이미 존재하고, 그 IdP 로
> Leantime 도 함께 로그인하게 하고 싶을 때만 적용하는 선택 절차다.** 공통 IdP 가 없으면 이 문서는
> 무시하고 [`leantime-codeploy.md`](leantime-codeploy.md) 의 기본 절차(Leantime 자체 계정 시스템)만
> 따르면 된다.
>
> ⚠ **이 저장소 환경에서는 실제 IdP/OIDC 제공자/LDAP 서버가 없어 아래 절차를 실행·검증할 수
> 없다.** 전 항목이 **운영자 검증 필요**다. 이 절은 [`office-leantime-architecture-review-2026-07-13.md`](office-leantime-architecture-review-2026-07-13.md)
> 가 정한 "공통 IdP 가 있을 때만 SSO 검토" 방향을 실무 절차로 구체화한 것이다.

---

## 1. 핵심 원칙 — 세션은 절대 공유하지 않는다

AeroOne 과 Leantime 은 [`leantime-codeploy.md`](leantime-codeploy.md) §1 이 정의한 대로 **코드/DB/
세션/포트가 완전히 분리된 두 개의 독립 스택**이다. 공통 IdP 를 도입하더라도 이 경계는 바뀌지
않는다.

- **AeroOne 의 `admin_session` 쿠키를 Leantime 에 전달·재사용하는 어떤 통합도 금지**한다(리버스
  프록시 헤더 주입, 쿠키 도메인 공유, iframe SSO 브릿지 등 포함).
- Leantime 은 **자기 자신의 OIDC/LDAP 클라이언트 설정**으로 IdP 와 직접 인증하고, **자기 자신의
  세션 쿠키**(Leantime 세션, AeroOne 과 다른 이름·다른 도메인/경로)를 발급한다.
- AeroOne 은 **자기 자신의 로그인/세션 체계**(현재의 `admin_session` + 로컬 계정)를 그대로 유지한다.
  IdP 연동 여부와 무관하게 AeroOne 인증 코드는 변경하지 않는다.
- 두 앱 사이의 유일한 통합 경로는 [`office-leantime-architecture-review-2026-07-13.md`](office-leantime-architecture-review-2026-07-13.md)
  가 권고하는 **읽기 전용 서버측 JSON-RPC 호출**(향후 Adapter, G004 스코프)이며, 이는 사용자
  브라우저 세션과 무관한 백엔드-대-백엔드 호출이다. **OIDC/LDAP 도입이 이 JSON-RPC 경계를
  확장하거나 세션을 엮는 근거가 되지 않는다.**
- 사용자 입장에서는 "같은 IdP 계정으로 각 앱에 각각 로그인"하는 경험이 된다 — 편의성은
  IdP 의 SSO(각 서비스가 독립적으로 IdP 에 리다이렉트해 토큰을 받는 표준 OIDC 흐름) 로 제공하고,
  **쿠키 공유로 편의성을 만들지 않는다.**

---

## 2. OIDC 적용 (권장 경로)

**(전 항목 운영자 검증 필요 — Leantime 버전별 OIDC 플러그인/설정 방식이 다를 수 있다.)**

1. IdP(예: Keycloak, Azure AD, Okta 등 사내 OIDC 제공자)에 Leantime 용 **신규 OIDC 클라이언트**를
   등록한다. Redirect URI 는 Leantime 자체 도메인/포트 기준(`http://<leantime-host>:8081/...`) 으로
   등록하고, AeroOne 도메인과 절대 겹치지 않게 한다.
2. Leantime 설정(관리자 콘솔 또는 `.env`/config, 버전별 상이)에 OIDC 클라이언트 ID/시크릿/
   discovery URL(또는 authorize/token/userinfo 개별 엔드포인트)을 등록한다. 이 자격증명은
   AeroOne 설정(`backend/.env`)과 **완전히 별개 파일/저장소**에 둔다.
3. IdP 응답 클레임(예: `groups`, `roles`)을 Leantime 의 **역할(role) 매핑 규칙**에 연결한다 —
   예: IdP `leantime-admin` 그룹 → Leantime Administrator, IdP `leantime-user` 그룹 → Leantime
   일반 사용자. AeroOne 의 RBAC 권한 키(`admin.*`, `office.use` 등)와는 **완전히 별개의 매핑
   테이블**이며 서로 참조하지 않는다.
4. 신규 사용자 최초 로그인 시 Leantime 측 **자동 프로비저닝 정책**(자동 계정 생성 허용 여부,
   기본 역할)을 명시적으로 결정하고 문서화한다.
5. AeroOne 쪽은 **아무것도 바꾸지 않는다.** `/leantime` 안내 페이지·health 프로브·대시보드 카드는
   기존과 동일하게 동작한다(OIDC 는 Leantime 내부 로그인 화면에만 영향).

## 3. LDAP 적용 (대안 경로)

**(전 항목 운영자 검증 필요.)**

1. Leantime 설정에서 LDAP/Active Directory 연동을 활성화하고, 사내 LDAP 서버 host/port/bind DN/
   검색 base 를 등록한다. 이 자격증명도 AeroOne 설정과 분리된 저장소에 둔다.
2. LDAP 그룹(예: `CN=LeantimeAdmins,OU=Groups,...`) → Leantime 역할 매핑을 구성한다.
3. Leantime 로그인 화면에서 LDAP 자격증명으로 인증하되, 발급되는 세션은 여전히 **Leantime 자체
   세션**이다 — LDAP 인증이 AeroOne 세션과 어떤 형태로도 연결되지 않는다.
4. OIDC 와 LDAP 를 동시에 켜는 경우 Leantime 쪽 로그인 화면에 두 방식이 모두 노출되는지, 계정
   충돌(같은 사용자명이 로컬 계정과 LDAP 계정 모두에 존재) 처리 정책을 운영자가 사전에 정의한다.

---

## 4. 검증 절차

배포 PC 에서 아래를 직접 확인해야 "OIDC/LDAP 통합 완료" 로 볼 수 있다. **본 저장소 환경에서는
실행 불가 — 전 항목 운영자 검증 필요.**

### 4.1 로그인 격리 확인 (Login isolation check)

- [ ] 같은 브라우저 세션에서 AeroOne(`http://<host>:29501`)에 로그인한 상태로 Leantime
      (`http://<host>:8081`)에 접속했을 때, **Leantime 이 자동 로그인되지 않고** 독립된 Leantime
      로그인 화면(또는 IdP 리다이렉트) 이 뜨는지 확인한다.
- [ ] 브라우저 개발자 도구에서 두 오리진의 쿠키 저장소를 비교해, AeroOne 의 `admin_session`
      쿠키와 Leantime 세션 쿠키가 **이름·값·도메인 모두 다른 별개 쿠키**인지 확인한다.
- [ ] IdP 로그인 화면에서 자격증명을 입력해 Leantime 에 로그인했을 때, 발급된 세션이 Leantime
      쿠키 저장소에만 생기고 AeroOne 쿠키에는 어떤 변화도 없는지 확인한다.

### 4.2 역할 매핑 확인 (Role-mapping check)

- [ ] IdP 의 관리자 그룹 소속 계정으로 로그인 시 Leantime 에서 Administrator 권한(프로젝트/사용자
      관리 메뉴 노출)을 갖는지 확인한다.
- [ ] IdP 의 일반 사용자 그룹 소속 계정으로 로그인 시 Leantime 에서 제한된 권한만 갖는지 확인한다.
- [ ] 그룹 매핑이 없는 계정(미지정 그룹)의 기본 역할이 최소 권한(least privilege)으로 떨어지는지
      확인한다 — 매핑 누락 시 관리자 권한이 기본값으로 부여되지 않아야 한다.
- [ ] Leantime 의 역할 변경이 AeroOne RBAC(`admin.*` 등 권한 키)에 어떤 영향도 주지 않는지
      확인한다(두 시스템의 권한 모델은 완전히 분리).

### 4.3 로그아웃 격리 확인 (Logout isolation check)

- [ ] Leantime 에서 로그아웃했을 때 AeroOne 세션이 그대로 유지되는지(로그아웃되지 않는지)
      확인한다.
- [ ] AeroOne 에서 로그아웃했을 때(헤더 **로그아웃** 버튼) Leantime 세션이 그대로 유지되는지
      확인한다.
- [ ] IdP 자체에서 세션을 종료(예: IdP 관리 콘솔에서 강제 로그아웃)했을 때, 이미 발급된 Leantime
      세션 쿠키가 즉시 무효화되는지 또는 다음 요청에서 재인증을 요구하는지 Leantime 버전별 동작을
      확인하고 문서화한다(OIDC Single Logout 미지원 버전이면 세션 만료 시간(TTL) 정책으로 보완).

---

## 5. 범위와 한계

- 이 절차는 **운영자 소유(operator-owned)** 이며, AeroOne 코드베이스의 배포/실행에 필수가
  아니다 — 공통 IdP 가 없으면 전체를 건너뛰어도 Leantime 동거 자체는 §2(OIDC)/§3(LDAP) 없이도
  [`leantime-codeploy.md`](leantime-codeploy.md) 만으로 완결된다.
- AeroOne 배포/기동/헬스체크/패키징 계약([`leantime-codeploy.md`](leantime-codeploy.md) §3, §8)은
  OIDC/LDAP 적용 여부와 **완전히 독립적**이다. 이 절차의 성공/실패는 AeroOne 이나 Leantime 의
  start/stop/status/backup/restore/rollback 스크립트 동작에 어떤 영향도 주지 않는다.
- 향후 읽기 전용 JSON-RPC Adapter(G004) 가 도입되더라도, 그 통합은 서버측 API 호출이며 이 문서가
  금지하는 "AeroOne 세션 쿠키 공유"와는 무관하다.

## 관련 문서

- Leantime 동거(co-deploy) 런북: [`leantime-codeploy.md`](leantime-codeploy.md)
- 통합 방향·SSO 검토 조건: [`office-leantime-architecture-review-2026-07-13.md`](office-leantime-architecture-review-2026-07-13.md)
- AeroOne 관리자 인증 정책: [`admin-auth.md`](admin-auth.md)
- AeroOne 폐쇄망 종합 가이드: [`../CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md)
