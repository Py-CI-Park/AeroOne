"""office-tools 모듈 — 보고서/차트/다이어그램 3종 도구의 공통 뼈대.

이 패키지는 상위 라우터(`api.router`), 파일 기반 작업 저장소(`core.job_store`),
활성 LLM 연결 브리지(`core.llm_bridge`)를 제공한다. 개별 도구의 생성 로직
(reports/charts/diagrams 의 `/generate` 등)은 다음 단계에서 각 서브라우터에 채운다.

모든 라우트는 세션 로그인(`get_current_user`)을 강제한다. 산출물은 DB 가 아니라
`backend/data/office_jobs/` 아래 파일 JobStore 에 저장하며, 각 job 은 세션 사용자
스코프로 소유권을 기록해 타인 접근을 403 으로 차단한다.
"""
