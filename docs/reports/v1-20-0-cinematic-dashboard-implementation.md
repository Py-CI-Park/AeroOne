# 1.20.0 시네마틱 항공 대시보드 구현 결과

- 분류: minor (`1.20.0`) UX/UI 고도화
- 기준 브랜치: `1.20.0-dev`
- 기능 브랜치: `feature/cinematic-dashboard`
- 시작 시각: `2026-07-22T22:20:15.9469460+09:00`
- 시작 기준 commit: `6efea8a9c5f51b5c9b444cb1a8dcafa045acab1d` (`시네마틱 항공 대시보드 연구 브랜치를 병합한다`)
- 종료 시각: 구현·검증 완료 후 기록
- 최종 commit: 구현·검증 완료 후 기록

## 1. 목표

1. 기존 Server Component, RBAC, degraded fallback 계약을 보존한다.
2. 홈 상단에 AeroOne의 항공 정체성을 전달하는 컴팩트 히어로를 추가한다.
3. 실제 권한을 통과한 핵심 모듈만 Featured 진입점으로 표시한다.
4. 영상·WebGL·신규 런타임 dependency 없이 포스터와 CSS 2.5D로 구현한다.
5. 모션 감소, 키보드 탐색, 저사양 환경에서도 업무 기능을 유지한다.
6. 기존 Recent Reads와 전체 모듈 그리드를 그대로 보존한다.

## 2. 기준 연구

- [`v1-20-0-cinematic-dashboard-research.md`](v1-20-0-cinematic-dashboard-research.md)
- 연구 결론: TravelX·Avora 계열 날개/구름 구도를 시각 언어로 사용하되, 실제 DOM 모듈과 기존 권한 경계를 유지하고 홈 Three.js·GSAP·가상 기능 카드는 제외한다.

## 3. 구현 변경

구현 완료 후 기록한다.

## 4. 1.19.1 대비 UX/UI 변화

구현 완료 후 기록한다.

## 5. 검증 결과

검증 완료 후 실제 명령과 결과만 기록한다.

## 6. 제외 범위와 후속 후보

구현 완료 후 기록한다.
