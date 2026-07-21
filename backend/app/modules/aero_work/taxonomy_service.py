"""업무 분류체계 마법사(gongmuwon §6.6) 서비스 — 니즈 파악 → LLM 후보 검토 → 적용.

① 니즈 파악(기관/부서/담당업무)을 받아, 색인된 파일(경로+요약)을 근거로 LLM 에 업무 분류
후보를 요청한다(② 검토). 사용자가 후보를 확정하면 ③ 적용으로 사용자 분류를 전량 교체한다
(멱등 — 재적용해도 결과가 같다). AeroOne provider 시스템(AiChatService + ProviderConfigService)
경유가 기본이며, 사용자 LLM 프로필이 local 이면 OllamaClient 로 강제한다(``prefs_service`` 와
동일한 계약). ``chat`` 콜러블 주입으로 테스트는 실 LLM 없이 결정적으로 돈다.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work.activity_service import record_activity
from app.modules.aero_work.models import (
    AeroWorkTaskCategory,
    AeroWorkTaskCategoryFile,
    KnowledgeFile,
    KnowledgeFolder,
)
from app.modules.aero_work.prefs_service import get_llm_mode
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import AiChatService, OllamaClient, OllamaError

logger = logging.getLogger(__name__)

_SYSTEM = (
    '너는 공공기관 지식관리 사서다. 기관·부서·담당업무 설명과 색인된 파일 목록을 보고, '
    '실제 업무 단위로 파일을 묶는 분류 후보를 만들어라. 각 분류는 이름(10자 내외 명사구)·설명'
    '(1~2문장)·해당 파일 id 목록을 갖는다. 다른 설명 없이 반드시 아래 JSON 배열 형식으로만 '
    '응답하라: [{"name": "...", "description": "...", "file_ids": [1, 2]}]'
)

_FENCE_RE = re.compile(r'^```[a-zA-Z]*\s*\n?|\n?```\s*$')
_MAX_INDEXED_FILES = 200
_MAX_NAME_CHARS = 100
_MAX_DESCRIPTION_CHARS = 2000

ChatCaller = Callable[[Settings, Session, list[AiChatMessage]], tuple[str, str]]


def _strip_fence(text: str) -> str:
    """마크다운 코드펜스(```json ... ```)를 벗겨 순수 JSON 텍스트만 남긴다."""

    stripped = (text or '').strip()
    return _FENCE_RE.sub('', stripped).strip()


def _default_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> tuple[str, str]:
    service = AiChatService(settings, db, ProviderConfigService(db, settings))
    answer, _ = service.chat(messages, [], False, 0)
    return answer, service.effective_model()


def _local_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> tuple[str, str]:
    return OllamaClient(settings).chat(messages), settings.ollama_default_model


def _indexed_files(db: Session, user_id: int) -> tuple[list[dict], bool]:
    """사용자 소유 색인 파일(최대 ``_MAX_INDEXED_FILES``건)과 잘림 여부를 반환한다."""
    rows = db.execute(
        select(KnowledgeFile.id, KnowledgeFile.rel_path, KnowledgeFile.summary)
        .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
        .where(KnowledgeFolder.owner_id == user_id)
        .order_by(KnowledgeFile.id)
        .limit(_MAX_INDEXED_FILES + 1)
    ).all()
    truncated = len(rows) > _MAX_INDEXED_FILES
    files = [
        {'id': row.id, 'rel_path': row.rel_path, 'summary': row.summary} for row in rows[:_MAX_INDEXED_FILES]
    ]
    return files, truncated


def build_propose_messages(
    organization: str, department: str, duties: str, files: list[dict]
) -> list[AiChatMessage]:
    """색인 파일 목록(경로+요약이 있으면 포함)을 근거로 후보 생성용 메시지를 조립한다."""

    if files:
        lines = []
        for file_row in files:
            line = f'- id={file_row["id"]} {file_row["rel_path"]}'
            if file_row.get('summary'):
                line += f' — {file_row["summary"]}'
            lines.append(line)
        file_list = '\n'.join(lines)
    else:
        file_list = '(색인된 파일이 없습니다)'
    user_content = (
        f'기관: {organization}\n부서: {department}\n담당업무:\n{duties}\n\n색인된 파일 목록:\n{file_list}'
    )
    return [
        AiChatMessage(role='system', content=_SYSTEM),
        AiChatMessage(role='user', content=user_content),
    ]


def _extract_bracket_span(text: str) -> str | None:
    """1차 JSON 파싱이 실패했을 때, 첫 ``[`` ~ 마지막 ``]`` 구간만 잘라 재시도 재료로 준다.

    LLM 이 배열 앞뒤에 군더더기 설명을 덧붙이는 경우(예: '다음과 같습니다: [...] 이상입니다.')를
    구제한다. 대괄호가 없거나 순서가 뒤집혀 있으면 ``None`` 을 반환해 상위에서 포기한다.
    """

    start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _parse_candidates(raw_answer: str, valid_file_ids: set[int]) -> tuple[list[dict], bool]:
    """LLM 응답을 후보 JSON 배열로 파싱한다. 반환값은 (후보 목록, 파싱 성공 여부).

    1차 파싱이 실패하면 첫 '[' ~ 마지막 ']' 구간만 잘라 2차로 재시도한다(설명 문구가 배열
    앞뒤에 섞여 나오는 LLM 응답을 구제). 그래도 실패하거나 배열이 아니면 (빈 후보, False) 를
    반환해 호출측이 'parse_error' 사유를 알 수 있게 한다.
    """

    text = _strip_fence(raw_answer)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        extracted = _extract_bracket_span(text)
        if extracted is None:
            logger.warning('taxonomy propose: LLM 응답 JSON 파싱 실패 — 빈 후보로 대체합니다.')
            return [], False
        try:
            data = json.loads(extracted)
        except (ValueError, TypeError):
            logger.warning('taxonomy propose: LLM 응답 2차 추출 파싱도 실패 — 빈 후보로 대체합니다.')
            return [], False
    if not isinstance(data, list):
        logger.warning('taxonomy propose: LLM 응답이 JSON 배열이 아닙니다 — 빈 후보로 대체합니다.')
        return [], False
    candidates: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()[:_MAX_NAME_CHARS]
        if not name:
            continue
        description = str(item.get('description') or '').strip()[:_MAX_DESCRIPTION_CHARS]
        raw_ids = item.get('file_ids')
        raw_ids = raw_ids if isinstance(raw_ids, list) else []
        # 실재 색인 file id 로만 필터한다 — LLM 이 지어낸/삭제된 id 는 조용히 버린다.
        file_ids = [fid for fid in raw_ids if isinstance(fid, int) and fid in valid_file_ids]
        candidates.append({'name': name, 'description': description, 'file_ids': file_ids})
    return candidates, True


def propose_categories(
    db: Session,
    settings: Settings,
    user_id: int,
    *,
    organization: str,
    department: str,
    duties: str,
    chat: ChatCaller | None = None,
) -> tuple[list[dict], str, str, bool]:
    """색인 파일을 근거로 업무 분류 후보를 만든다. 실패해도 예외 없이 빈 후보를 반환한다.

    반환값은 (후보 목록, 모델명, reason, truncated). ``reason`` 은 'ok'|'ai_disabled'|
    'llm_error'|'parse_error' 중 하나로, 마법사 ②검토 화면이 실패 원인별로 구분된 안내를
    보이고 수동 후보 추가로 계속 진행할 수 있게 한다. ``truncated`` 는 색인 파일이 상한
    (``_MAX_INDEXED_FILES``)을 넘어 일부만 근거로 쓰였는지 여부다.
    """

    files, truncated = _indexed_files(db, user_id)
    valid_file_ids = {file_row['id'] for file_row in files}
    if not settings.ai_features_enabled:
        logger.warning('taxonomy propose: AI 기능이 비활성화되어 있습니다 — 빈 후보를 반환합니다.')
        return [], '', 'ai_disabled', truncated
    messages = build_propose_messages(organization, department, duties, files)
    caller = chat if chat is not None else (_local_chat if get_llm_mode(db, user_id) == 'local' else _default_chat)
    try:
        answer, model = caller(settings, db, messages)
    except OllamaError as exc:
        logger.warning('taxonomy propose: LLM 호출 실패(%s) — 빈 후보를 반환합니다.', exc)
        return [], '', 'llm_error', truncated
    except Exception as exc:  # noqa: BLE001 — provider 계열 오류 전부 완화(치명 아님)
        logger.warning('taxonomy propose: LLM 호출 예외(%s) — 빈 후보를 반환합니다.', exc)
        return [], '', 'llm_error', truncated
    candidates, parsed_ok = _parse_candidates(answer, valid_file_ids)
    reason = 'ok' if parsed_ok else 'parse_error'
    return candidates, model, reason, truncated


def apply_categories(db: Session, user_id: int, categories: list[dict]) -> int:
    """사용자의 기존 업무 분류를 전량 교체한다(멱등 — 몇 번을 다시 적용해도 결과가 같다).

    기존 분류는 ORM delete-orphan/DB CASCADE 어느 쪽에도 기대지 않고 매핑(``…_files``)을
    먼저 bulk delete 한 뒤 분류 본체를 bulk delete 한다 — SQLite 는 연결별 PRAGMA
    foreign_keys 설정이 꺼져 있으면 CASCADE 가 조용히 무시되므로, 순서를 코드로 못박는다.
    """

    existing_ids = [
        cid for (cid,) in db.execute(
            select(AeroWorkTaskCategory.id).where(AeroWorkTaskCategory.user_id == user_id)
        ).all()
    ]
    if existing_ids:
        db.execute(
            sa_delete(AeroWorkTaskCategoryFile).where(AeroWorkTaskCategoryFile.category_id.in_(existing_ids))
        )
        db.execute(sa_delete(AeroWorkTaskCategory).where(AeroWorkTaskCategory.id.in_(existing_ids)))
    db.flush()

    valid_file_ids = {
        fid
        for (fid,) in db.execute(
            select(KnowledgeFile.id)
            .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
            .where(KnowledgeFolder.owner_id == user_id)
        ).all()
    }
    created = 0
    for order, category in enumerate(categories):
        name = str(category.get('name') or '').strip()[:_MAX_NAME_CHARS]
        if not name:
            continue
        row = AeroWorkTaskCategory(
            user_id=user_id,
            name=name,
            description=str(category.get('description') or '').strip()[:_MAX_DESCRIPTION_CHARS],
            sort_order=order,
        )
        db.add(row)
        db.flush()
        raw_ids = category.get('file_ids') or []
        file_ids = [fid for fid in dict.fromkeys(raw_ids) if fid in valid_file_ids]
        for file_id in file_ids:
            db.add(AeroWorkTaskCategoryFile(category_id=row.id, file_id=file_id))
        created += 1
    db.flush()
    record_activity(db, user_id, 'taxonomy.apply', f'업무 분류 적용 — {created}건')
    return created


def list_categories(db: Session, user_id: int) -> list[dict]:
    """사용자 업무 분류를 순서대로, 각 분류에 딸린 파일(경로/폴더명/요약)과 함께 반환한다.

    분류마다 파일 조회 쿼리를 따로 날리지 않고, 매핑+파일+폴더를 한 번의 IN 조인으로 가져와
    메모리에서 category_id 별로 그룹핑한다(N+1 회피).
    """

    categories = db.execute(
        select(AeroWorkTaskCategory)
        .where(AeroWorkTaskCategory.user_id == user_id)
        .order_by(AeroWorkTaskCategory.sort_order, AeroWorkTaskCategory.id)
    ).scalars().all()
    if not categories:
        return []
    category_ids = [category.id for category in categories]
    file_rows = db.execute(
        select(AeroWorkTaskCategoryFile.category_id, KnowledgeFile, KnowledgeFolder.name)
        .join(KnowledgeFile, AeroWorkTaskCategoryFile.file_id == KnowledgeFile.id)
        .join(KnowledgeFolder, KnowledgeFolder.id == KnowledgeFile.folder_id)
        .where(
            AeroWorkTaskCategoryFile.category_id.in_(category_ids),
            KnowledgeFolder.owner_id == user_id,
        )
        .order_by(KnowledgeFile.rel_path)
    ).all()
    files_by_category: dict[int, list[dict]] = {}
    for category_id, file_row, folder_name in file_rows:
        files_by_category.setdefault(category_id, []).append(
            {'id': file_row.id, 'rel_path': file_row.rel_path, 'folder_name': folder_name, 'summary': file_row.summary}
        )
    return [
        {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'sort_order': category.sort_order,
            'files': files_by_category.get(category.id, []),
        }
        for category in categories
    ]


def delete_category(db: Session, user_id: int, category_id: int) -> bool:
    """소유자 스코프로 분류 1건을 삭제한다. 존재하지 않거나 소유자가 다르면 False."""

    row = db.get(AeroWorkTaskCategory, category_id)
    if row is None or row.user_id != user_id:
        return False
    name = row.name
    db.delete(row)
    db.flush()
    record_activity(db, user_id, 'taxonomy.delete', f'업무 분류 삭제 "{name}"')
    return True
