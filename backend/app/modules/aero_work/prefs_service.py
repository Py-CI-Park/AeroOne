"""사용자별 Aero Work 환경설정 — LLM 프로필(default/local) 전환.

gongmuwon 환경설정의 "LLM 프로필 전환"(§8.2)을 AeroOne 계약 위에 얹는다:
- ``default``: 관리자가 선택한 provider(로컬 Ollama 또는 OpenAI 호환 연결)를 그대로 따른다.
- ``local``: 이 사용자에 한해 로컬 Ollama(env)로 강제한다(민감 업무를 외부/내부서버로
  보내고 싶지 않을 때).

연결 등록·기본 선택의 진실 원천은 여전히 관리자 콘솔이다(사용자는 위 두 모드만 고른다).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.aero_work.models import AeroWorkUserPref

LLM_MODES = ('default', 'local')


def get_llm_mode(db: Session, user_id: int) -> str:
    row = db.get(AeroWorkUserPref, user_id)
    return row.llm_mode if row is not None and row.llm_mode in LLM_MODES else 'default'


def set_llm_mode(db: Session, user_id: int, mode: str) -> str:
    if mode not in LLM_MODES:
        raise ValueError(f'지원하지 않는 LLM 모드: {mode}')
    row = db.get(AeroWorkUserPref, user_id)
    if row is None:
        row = AeroWorkUserPref(user_id=user_id, llm_mode=mode)
        db.add(row)
    else:
        row.llm_mode = mode
    db.flush()
    return mode
