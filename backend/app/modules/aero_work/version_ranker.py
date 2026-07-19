"""최신본 판별 — 파일명에서 날짜·버전·'최종/최신' 표식을 읽어 같은 문서의 최신 판본을 표시한다.

gongmuwon 의 "여러 판본 중 최신본 판별"(사용설명서 §4.2)을 규칙 기반으로 재현한다. 같은 기본
이름(base)으로 묶고, 그룹에 판본이 둘 이상일 때만 최고 키를 ``is_latest=True`` 로 표시한다.
"""

from __future__ import annotations

import re

_DATE_RE = re.compile(r'(20\d{2})[.\-_ ]?(\d{2})[.\-_ ]?(\d{2})')
_VER_RE = re.compile(r'[vV]\s*(\d+)(?:[.\-](\d+))?')
_PAREN_RE = re.compile(r'\((\d+)\)')
_FINAL_WORDS = ('최종', '최신', '확정', 'final', 'FINAL', 'Final')


def _analyze(rel_path: str) -> tuple[str, tuple[int, int, int, int]]:
    name = re.split(r'[\\/]', rel_path)[-1]
    stem = name.rsplit('.', 1)[0]

    final = 1 if any(word in stem for word in _FINAL_WORDS) else 0

    date_num = 0
    date_match = _DATE_RE.search(stem)
    if date_match:
        try:
            date_num = int(date_match.group(1)) * 10000 + int(date_match.group(2)) * 100 + int(date_match.group(3))
        except ValueError:
            date_num = 0

    version = 0
    version_match = _VER_RE.search(stem)
    if version_match:
        version = int(version_match.group(1)) * 1000 + int(version_match.group(2) or 0)

    paren = 0
    paren_match = _PAREN_RE.search(stem)
    if paren_match:
        paren = int(paren_match.group(1))

    base = stem
    base = _DATE_RE.sub('', base)
    base = _VER_RE.sub('', base)
    base = _PAREN_RE.sub('', base)
    for word in _FINAL_WORDS:
        base = base.replace(word, '')
    base = re.sub(r'[\s_\-.()]+', '', base).lower()

    return base, (final, date_num, version, paren)


def mark_latest(hits: list[dict]) -> list[dict]:
    """검색 결과(dict 리스트)에 ``is_latest`` 를 채운다.

    같은 base 로 묶어 판본이 둘 이상인 그룹에서만 최고 키를 최신본으로 표시한다(단일 문서는
    비교 대상이 없으므로 표시하지 않는다).
    """

    groups: dict[str, list[tuple[tuple[int, int, int, int], dict]]] = {}
    for hit in hits:
        hit.setdefault('is_latest', False)
        base, key = _analyze(str(hit.get('rel_path', '')))
        groups.setdefault(base, []).append((key, hit))

    for items in groups.values():
        if len(items) < 2:
            continue
        best_hit = max(items, key=lambda pair: pair[0])[1]
        best_hit['is_latest'] = True

    return hits


def group_by_family(items: list[dict]) -> list[dict]:
    """파일 dict 리스트를 버전 가족으로 묶는다(gongmuwon 업무 허브의 '대표 + 버전 이력').

    같은 base 로 묶어 각 가족의 대표(대표=최고 키=공식본)를 앞세우고, 나머지를 최신순 판본
    이력으로 정렬한다. 반환: ``[{'base', 'representative', 'items'(최신순), 'has_versions'}]``.
    """

    groups: dict[str, list[tuple[tuple[int, int, int, int], dict]]] = {}
    for item in items:
        item.setdefault('is_latest', False)
        base, key = _analyze(str(item.get('rel_path', '')))
        groups.setdefault(base, []).append((key, item))

    families: list[dict] = []
    for base, entries in groups.items():
        ordered = [entry[1] for entry in sorted(entries, key=lambda pair: pair[0], reverse=True)]
        representative = ordered[0]
        has_versions = len(ordered) > 1
        if has_versions:
            representative['is_latest'] = True
        families.append(
            {
                'base': base,
                'representative': representative,
                'items': ordered,
                'has_versions': has_versions,
            }
        )
    families.sort(key=lambda family: str(family['representative'].get('rel_path', '')))
    return families
