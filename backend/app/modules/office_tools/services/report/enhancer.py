"""보고서 AI 편집 — MVP ``svc01/enhancer.py`` 를 AeroOne 활성 연결로 포팅.

MVP 는 자체 ``OpenAICompatibleLLM.json_call`` 을 썼지만, AeroOne 은 산출물 A(LLM
연결 레지스트리)의 ``OpenAiCompatibleClient.chat`` 를 쓴다. 따라서 여기서는 ``chat`` 로
문자열 응답을 받아 JSON 을 직접 파싱한다(다이어그램 서비스와 동일한 방식).

핵심 안전 규칙(MVP 그대로 유지):
- 원문에 없는 수치가 편집 결과에 새로 생기면 그 문서 조각은 편집을 **폐기하고 원문을
  유지**한다(수치 환각 차단).
- 편집 결과에 실행 가능한 HTML(script/iframe/object/embed)이 있으면 원문을 유지한다.
- 활성 연결이 없거나(``client=None``) 호출이 실패하면 원문을 유지하고 경고를 남긴다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.modules.ai.openai_client import OpenAiCompatibleClient

_SYSTEM_PROMPT = """당신은 사내 기술·업무 보고서 편집기다. 입력 Markdown을 개선하되 다음 규칙을 절대 준수한다.
1. 원문의 사실, 고유명사, 수치, 날짜, 단위, 판정 결과를 바꾸거나 새로 만들지 않는다.
2. 모르는 내용을 추정하거나 보충하지 않는다. 불명확하면 문장만 명료하게 정리한다.
3. Markdown 구조와 코드펜스(mermaid/chart 포함)를 보존한다.
4. HTML, JavaScript, 외부 URL, shell 명령을 생성하지 않는다.
5. JSON 객체 하나만 반환한다: {"markdown": "개선된 Markdown", "warnings": ["검토 경고"]}.
6. raw reasoning이나 내부 사고 과정은 반환하지 않는다."""

_MODE_INSTRUCTION = {
    'polish': '문체, 맞춤법, 제목 계층과 가독성을 개선한다. 내용 축약은 최소화한다.',
    'executive': '핵심 결론이 먼저 보이도록 재구성하되 원문 정보만 사용한다. 필요하면 원문 범위 안에서 요약 문단을 만든다.',
}


@dataclass
class EnhancementResult:
    """편집 결과와 검증 메타. 라우트/서비스가 manifest 와 job 경고에 사용한다."""

    markdown: str
    warnings: list[str] = field(default_factory=list)
    llm_used: bool = False
    model: str | None = None


def _split_sections(markdown_text: str, max_chars: int = 28_000) -> list[str]:
    """``## `` 헤더 경계로 문서를 조각낸다(너무 길면 문단 경계로 추가 분할)."""

    parts = re.split(r'(?=^##\s+)', markdown_text, flags=re.M)
    chunks: list[str] = []
    current = ''
    for part in parts:
        if not part:
            continue
        if current and len(current) + len(part) > max_chars:
            chunks.append(current.rstrip() + '\n')
            current = part
        else:
            current += part
    if current:
        chunks.append(current.rstrip() + '\n')

    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
            continue
        current = ''
        for paragraph in re.split(r'(\n\s*\n)', chunk):
            if current and len(current) + len(paragraph) > max_chars:
                final.append(current)
                current = paragraph
            else:
                current += paragraph
        if current:
            final.append(current)
    return final or [markdown_text]


def _numeric_tokens(text: str) -> set[str]:
    """텍스트의 숫자 토큰 집합(부호/천단위/소수/퍼센트 포함)을 돌려준다."""

    return set(re.findall(r'(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?%?', text))


def _extract_json(text: str) -> dict:
    """LLM 응답에서 첫 JSON 객체를 파싱한다(코드펜스/잡음 허용)."""

    candidate = text.strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```[a-zA-Z0-9]*\s*|\s*```$', '', candidate).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', candidate, flags=re.S)
        if not match:
            raise ValueError('LLM 응답에서 JSON 객체를 찾지 못했습니다')
        return json.loads(match.group(0))


def enhance_markdown(
    markdown_text: str,
    mode: str,
    client: OpenAiCompatibleClient | None,
) -> EnhancementResult:
    """모드에 따라 Markdown 을 AI 편집한다. 위험 조각은 원문을 유지한다."""

    if mode == 'none':
        return EnhancementResult(markdown=markdown_text)
    if client is None:
        return EnhancementResult(
            markdown=markdown_text,
            warnings=['AI 개선을 요청했지만 활성 LLM 연결이 없어 원문으로 변환했습니다.'],
        )

    instruction = _MODE_INSTRUCTION.get(mode, '문체와 구조를 개선한다.')
    output_chunks: list[str] = []
    warnings: list[str] = []
    model: str | None = None
    used = False

    for index, chunk in enumerate(_split_sections(markdown_text), start=1):
        user_prompt = (
            f'편집 모드: {mode}\n편집 지침: {instruction}\n문서 조각: {index}\n\n'
            f'--- 입력 Markdown ---\n{chunk}\n--- 입력 끝 ---'
        )
        try:
            content = client.chat(
                [
                    {'role': 'system', 'content': _SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                max_tokens=4096,
            )
            payload = _extract_json(content)
            candidate = str(payload.get('markdown') or '').strip()
            if not candidate:
                raise ValueError('편집 응답에 markdown 이 없습니다')
            introduced = _numeric_tokens(candidate) - _numeric_tokens(chunk)
            if introduced:
                warnings.append(
                    f'문서 조각 {index}에서 원문에 없는 수치 {sorted(introduced)[:8]}가 감지되어 해당 조각은 원문을 유지했습니다.'
                )
                output_chunks.append(chunk)
                continue
            if re.search(r'<\s*(script|iframe|object|embed)\b', candidate, flags=re.I):
                warnings.append(f'문서 조각 {index}에서 실행 가능한 HTML이 감지되어 원문을 유지했습니다.')
                output_chunks.append(chunk)
                continue
            output_chunks.append(candidate.rstrip() + '\n')
            warnings.extend(str(item) for item in (payload.get('warnings') or []) if str(item).strip())
            used = True
        except Exception as exc:  # noqa: BLE001 - 조각 단위 폴백 신호로 흡수
            warnings.append(f'문서 조각 {index} AI 개선 실패로 원문을 유지했습니다: {exc}')
            output_chunks.append(chunk)

    return EnhancementResult(
        markdown='\n'.join(output_chunks).strip() + '\n',
        warnings=list(dict.fromkeys(warnings)),
        llm_used=used,
        model=model,
    )
