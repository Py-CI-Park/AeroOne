from __future__ import annotations

import pytest

from app.modules.ai.service import ThinkBlockStreamFilter, _strip_think_blocks


def _run(chunks: list[str]) -> str:
    filt = ThinkBlockStreamFilter()
    out = []
    for chunk in chunks:
        out.append(filt.feed(chunk))
    out.append(filt.flush())
    return ''.join(out)


@pytest.mark.parametrize(
    'open_tag,close_tag',
    [
        ('<think>', '</think>'),
        ('<thinking>', '</thinking>'),
        ('< think >', '</ think >'),
        ('<  think  >', '<  /  think  >'),
        ('<THINK>', '</THINK>'),
        ('<THINK  >', '</THINK  >'),
        ('<thinking >', '</thinking >'),
        ('<\tthink\n>', '</\tthink\n>'),
    ],
)
def test_whitespace_and_case_variants_are_hidden(open_tag: str, close_tag: str) -> None:
    visible = _run([f'hello {open_tag}secret{close_tag} world'])
    assert 'secret' not in visible
    assert visible == 'hello  world'


def test_whitespace_variant_matches_non_streaming_regex_parity() -> None:
    # 스트리밍 필터는 비스트리밍 _strip_think_blocks 와 동일한 허용 범위를 가져야 한다.
    text = 'answer < think >hidden reasoning</ think > done'
    assert _strip_think_blocks(text).strip() == 'answer  done'
    assert _run([text]) == 'answer  done'


def test_nested_think_blocks_close_at_first_close_tag_matching_regex_semantics() -> None:
    # 비스트리밍 정규식(.*? 비탐욕)과 동일하게 "첫 번째" 닫는 태그에서 종료한다 — 중첩된
    # 안쪽 open 태그는 별도로 추적하지 않는다(정규식과의 동작 동등성을 시험으로 고정한다).
    text = '<think>outer <think>inner</think> still-hidden</think>final'
    non_streaming = _strip_think_blocks(text)
    streamed = _run([text])
    assert non_streaming == streamed
    assert 'inner' not in streamed
    assert 'outer' not in streamed
    # 첫 </think> 에서 종료되므로 그 뒤의 "still-hidden</think>" 는 (비스트리밍 정규식과
    # 마찬가지로) 일반 텍스트로 노출된다 — 이는 depth 를 추적하지 않는 알려진 동작이며,
    # 스트리밍 필터가 비스트리밍 규칙과 어긋나지 않음을 고정하는 것이 이 테스트의 목적이다.
    assert 'still-hidden' in streamed
    assert streamed.endswith('final')


def test_orphan_closing_tag_without_matching_open_is_passed_through_as_text() -> None:
    visible = _run(['no open tag here </think> literal'])
    assert visible == 'no open tag here </think> literal'


def test_flush_discards_unterminated_open_tag_and_body() -> None:
    filt = ThinkBlockStreamFilter()
    assert filt.feed('before <think>reasoning never closes') == 'before '
    assert filt.flush() == ''


def test_flush_returns_trailing_plain_text_outside_think_block() -> None:
    filt = ThinkBlockStreamFilter()
    assert filt.feed('<think>hidden</think>trailing text') == 'trailing text'
    assert filt.flush() == ''


def test_flush_returns_dangling_unconfirmed_open_prefix_as_plain_text() -> None:
    # '<thi' 는 아직 여는 태그로 확정되지 않은 접두(공백이 이어질 수도 있었다) — think 블록
    # "내부"로 진입한 적이 없으므로(self._inside=False) flush() 는 이를 일반 텍스트로 취급한다.
    filt = ThinkBlockStreamFilter()
    assert filt.feed('answer <thi') == 'answer '
    assert filt.flush() == '<thi'


def test_chunk_boundary_split_across_open_and_close_tags_never_leaks() -> None:
    chunks = ['hello <thi', 'nk>secret</th', 'ink> world']
    assert _run(chunks) == 'hello  world'


def test_whitespace_tag_split_one_character_per_chunk_across_100_chunks() -> None:
    text = 'prefix < think  >leaked-reasoning-content</  think > suffix'
    chunks = list(text)
    assert len(chunks) < 100
    # 100개 청크로 맞추기 위해 마지막 몇 개는 빈 문자열 청크를 섞어 넣어도 동일해야 한다
    # (빈 청크는 feed() 에서 즉시 무시된다).
    padded = chunks + [''] * (100 - len(chunks))
    assert len(padded) == 100
    visible = _run(padded)
    assert 'leaked-reasoning-content' not in visible
    assert visible == 'prefix  suffix'


def test_one_char_per_chunk_100_chunks_plain_text_survives_untouched() -> None:
    text = 'x' * 100
    chunks = list(text)
    assert len(chunks) == 100
    assert _run(chunks) == text


def test_invalid_lookalike_tag_is_not_treated_as_think_block() -> None:
    # '<thinker>' 는 'think' 접두어를 갖지만 'thinking'/'think' 정확한 단어가 아니므로 무효.
    visible = _run(['before <thinker> after'])
    assert visible == 'before <thinker> after'


def test_slash_inside_open_tag_position_is_rejected() -> None:
    # 여는 태그 자리에 '/' 가 오면(닫는 태그 문법) 여는 태그로 매치되지 않는다.
    visible = _run(['</think> literal since nothing was open'])
    assert visible == '</think> literal since nothing was open'
