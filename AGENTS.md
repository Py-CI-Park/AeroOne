# AeroOne Repository Instructions

## Commit Message Rule

- 앞으로 이 저장소에서 만드는 모든 커밋 메시지는 **항상 한국어 제목과 한국어 본문**으로 작성한다.
- 커밋 첫 줄은 변경의 **의도(왜 이 변경을 하는지)**를 한국어로 분명하게 적는다.
- 커밋 본문은 한글 문장으로 충분한 맥락을 제공해야 하며, 최소한 아래를 설명하도록 한다.
  - 무엇이 바뀌는가
  - 왜 지금 이 변경이 필요한가
  - 어떤 제약이나 트레이드오프를 고려했는가
- 저장소에서 요구하는 Lore commit trailer 형식은 유지하되, trailer의 **값(value)은 한국어로 자세히 작성**한다.
  - 예: `Constraint: Windows CMD quoting 제약 때문에 wrapper 분리가 필요했다`
  - 예: `Rejected: 긴 cmd /k 인라인 문자열 유지 | quoting 재발 위험이 커서 배제`
- 한 줄짜리 영문 커밋이나, 의미 없는 축약형 메시지, 배경 설명이 없는 메시지는 허용하지 않는다.

## Pull Request Text Rule

- PR 제목과 본문도 가능한 한 한국어로 작성한다.
- PR 본문은 마크다운 형식으로, 변경 배경 / 핵심 수정 사항 / 검증 결과를 상세히 정리한다.
