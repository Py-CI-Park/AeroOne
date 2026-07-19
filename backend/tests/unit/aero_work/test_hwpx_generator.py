"""HWPX(OWPML) 생성기 — 구조 유효성 단위 검증.

한컴 실기 렌더 호환은 이 환경에서 검증 불가(한컴 없음)이므로, 여기서는 OCF/OWPML 구조 유효성
(유효 ZIP · mimetype 선두 stored · 필수 파트 · XML well-formed · 본문 주입 · 이스케이프)만 본다.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile

from app.modules.aero_work.hwpx_generator import MIMETYPE, build_hwpx, split_paragraphs

REQUIRED_PARTS = {
    'mimetype',
    'version.xml',
    'settings.xml',
    'Contents/content.hpf',
    'Contents/header.xml',
    'Contents/section0.xml',
    'META-INF/container.xml',
    'META-INF/manifest.xml',
}


def _archive(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


def test_mimetype_is_first_stored_entry() -> None:
    zf = _archive(build_hwpx('제목', '문단'))
    first = zf.infolist()[0]
    assert first.filename == 'mimetype'
    assert first.compress_type == zipfile.ZIP_STORED
    assert zf.read('mimetype').decode('utf-8') == MIMETYPE


def test_required_parts_present_and_wellformed() -> None:
    zf = _archive(build_hwpx('제목', '본문 한 줄'))
    assert REQUIRED_PARTS <= set(zf.namelist())
    for name in zf.namelist():
        if name.endswith(('.xml', '.hpf')):
            ET.fromstring(zf.read(name))  # well-formed 아니면 예외


def test_title_and_body_injected() -> None:
    zf = _archive(build_hwpx('출장 결과 보고', '대전 방문함.\n특이사항 없음.'))
    section = zf.read('Contents/section0.xml').decode('utf-8')
    assert '출장 결과 보고' in section
    assert '대전 방문함.' in section
    assert '특이사항 없음.' in section


def test_xml_special_chars_are_escaped() -> None:
    zf = _archive(build_hwpx('제목 <&>', 'a < b & c'))
    raw = zf.read('Contents/section0.xml')
    ET.fromstring(raw)  # 이스케이프 실패면 파싱 예외
    text = raw.decode('utf-8')
    assert '&lt;' in text and '&amp;' in text


def test_empty_input_falls_back_to_untitled() -> None:
    zf = _archive(build_hwpx('', ''))
    section = zf.read('Contents/section0.xml').decode('utf-8')
    ET.fromstring(section.encode('utf-8'))
    assert '무제' in section


def test_split_paragraphs_drops_blank_lines() -> None:
    assert split_paragraphs('a\n\n b \n\nc') == ['a', 'b', 'c']
    assert split_paragraphs('') == []
    assert split_paragraphs('   \n\t') == []
