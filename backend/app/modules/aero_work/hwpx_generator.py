"""HWPX(OWPML) 문서 생성 — 제목 + 문단 본문을 최소 OWPML 패키지(ZIP+XML)로 조립한다.

HWPX 는 OWPML(ZIP + XML) 포맷이라 python-docx 처럼 ZIP+XML 을 직접 조립할 수 있고, 외부
SaaS·인터넷이 필요 없어 폐쇄망에 적합하다. 본 모듈은 구조적으로 유효한 최소 패키지를 만든다:

  mimetype(stored) · version.xml · settings.xml · Contents/header.xml · Contents/section0.xml
  · Contents/content.hpf · META-INF/container.xml · META-INF/manifest.xml

본문 문단은 section0 에 charPr/paraPr/style id=0 을 참조해 주입한다.

검증 경계: 구조 유효성(유효한 ZIP·mimetype 선두 stored·필수 파트 존재·XML well-formed·ID 참조
해소)은 테스트로 보장한다. 다만 **한컴 오피스 실제 렌더 호환성은 실기(한컴 설치 PC)에서 확인**
해야 한다 — 본 개발 환경에는 한컴이 없어 오픈 렌더를 검증할 수 없다.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

MIMETYPE = 'application/hwp+zip'

_LANGS = ('HANGUL', 'LATIN', 'HANJA', 'JAPANESE', 'OTHER', 'SYMBOL', 'USER')


def _xml(value: str) -> str:
    return escape(value or '', {'"': '&quot;', "'": '&apos;'})


def _version_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version"'
        ' tagetApplication="WORDPROCESSOR" major="5" minor="0" micro="5" buildNumber="0"'
        ' os="1" xmlVersion="1.4" application="Aero Work" appVersion="1.0"/>'
    )


def _settings_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app">'
        '<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
        '</ha:HWPApplicationSetting>'
    )


def _container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<ocf:rootfiles>'
        '<ocf:rootfile full-path="Contents/content.hpf"'
        ' media-type="application/hwpml-package+xml"/>'
        '</ocf:rootfiles>'
        '</ocf:container>'
    )


def _manifest_xml() -> str:
    items = [
        ('Contents/header.xml', 'application/xml'),
        ('Contents/section0.xml', 'application/xml'),
        ('Contents/content.hpf', 'application/hwpml-package+xml'),
        ('settings.xml', 'application/xml'),
        ('version.xml', 'application/xml'),
    ]
    entries = ''.join(
        f'<odf:file-entry odf:full-path="{path}" odf:media-type="{mtype}"/>'
        for path, mtype in items
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"'
        ' odf:version="1.2">'
        f'{entries}'
        '</odf:manifest>'
    )


def _content_hpf(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hpf:package xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"'
        ' xmlns:opf="http://www.idpf.org/2007/opf/" version="" unique-identifier="" id="">'
        '<hpf:metadata>'
        f'<opf:title>{_xml(title)}</opf:title>'
        '<opf:language>ko</opf:language>'
        '</hpf:metadata>'
        '<hpf:manifest>'
        '<hpf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
        '<hpf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
        '<hpf:item id="settings" href="settings.xml" media-type="application/xml"/>'
        '</hpf:manifest>'
        '<hpf:spine>'
        '<hpf:itemref idref="header"/>'
        '<hpf:itemref idref="section0"/>'
        '</hpf:spine>'
        '</hpf:package>'
    )


def _fontfaces() -> str:
    faces = []
    for lang in _LANGS:
        faces.append(
            f'<hh:fontface lang="{lang}" fontCnt="1">'
            '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0">'
            '<hh:typeInfo familyType="FCAP_UNKNOWN" weight="0" proportion="0" contrast="0"'
            ' strokeVariation="0" armStyle="0" letterform="0" midline="0" xHeight="0"/>'
            '</hh:font>'
            '</hh:fontface>'
        )
    return f'<hh:fontfaces itemCnt="{len(_LANGS)}">' + ''.join(faces) + '</hh:fontfaces>'


def _char_pr() -> str:
    fontref = (
        '<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    )
    ratio = '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
    spacing = '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    relsz = '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
    offset = '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    return (
        '<hh:charProperties itemCnt="1">'
        '<hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none"'
        ' useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">'
        f'{fontref}{ratio}{spacing}{relsz}{offset}'
        '</hh:charPr>'
        '</hh:charProperties>'
    )


def _para_pr() -> str:
    return (
        '<hh:paraProperties itemCnt="1">'
        '<hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1"'
        ' suppressLineNumbers="0" checked="0">'
        '<hh:align horizontal="JUSTIFY" vertical="BASELINE"/>'
        '<hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD"'
        ' widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:margin>'
        '<hc:intent value="0" unit="HWPUNIT"/>'
        '<hc:left value="0" unit="HWPUNIT"/><hc:right value="0" unit="HWPUNIT"/>'
        '<hc:prev value="0" unit="HWPUNIT"/><hc:next value="0" unit="HWPUNIT"/>'
        '</hh:margin>'
        '<hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>'
        '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0"'
        ' offsetBottom="0" connect="0" ignoreMargin="0"/>'
        '</hh:paraPr>'
        '</hh:paraProperties>'
    )


def _border_fills() -> str:
    return (
        '<hh:borderFills itemCnt="2">'
        '<hh:borderFill id="1" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '</hh:borderFill>'
        '<hh:borderFill id="2" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:rightBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:topBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:bottomBorder type="NONE" width="0.1 mm" color="#000000"/>'
        '<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
        '</hh:borderFill>'
        '</hh:borderFills>'
    )


def _header_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
        ' xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" version="1.4" secCnt="1">'
        '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>'
        '<hh:refList>'
        f'{_fontfaces()}'
        f'{_border_fills()}'
        f'{_char_pr()}'
        '<hh:tabProperties itemCnt="1">'
        '<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>'
        '</hh:tabProperties>'
        f'{_para_pr()}'
        '<hh:styles itemCnt="1">'
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0"'
        ' charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>'
        '</hh:styles>'
        '</hh:refList>'
        '</hh:head>'
    )


def _paragraph(text: str, *, first: bool = False) -> str:
    sec_pr = ''
    if first:
        sec_pr = (
            '<hp:run charPrIDRef="0">'
            '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000"'
            ' tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0"'
            ' textVerticalWidthHead="0" masterPageCnt="0">'
            '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0" strtnum="0"/>'
            '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
            '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0"'
            ' border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0"'
            ' showLineNumber="0"/>'
            '<hp:pagePr landscape="WIDELY" width="59528" height="84188" gutterType="LEFT_ONLY">'
            '<hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504"'
            ' top="5668" bottom="4252"/>'
            '</hp:pagePr>'
            '</hp:secPr>'
            '</hp:run>'
        )
    return (
        '<hp:p id="0" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'{sec_pr}'
        '<hp:run charPrIDRef="0">'
        f'<hp:t>{_xml(text)}</hp:t>'
        '</hp:run>'
        '<hp:linesegarray>'
        '<hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000"'
        ' baseline="850" spacing="600" horzpos="0" horzsize="42520" flags="393216"/>'
        '</hp:linesegarray>'
        '</hp:p>'
    )


def _section_xml(paragraphs: list[str]) -> str:
    body_paras = [p for p in paragraphs if p.strip()]
    if not body_paras:
        body_paras = ['']
    rendered = ''.join(
        _paragraph(text, first=(index == 0)) for index, text in enumerate(body_paras)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
        ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
        ' xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core">'
        f'{rendered}'
        '</hs:sec>'
    )


def split_paragraphs(body: str) -> list[str]:
    """본문 텍스트를 빈 줄/개행 기준 문단 리스트로 나눈다."""

    lines = [line.strip() for line in (body or '').splitlines()]
    return [line for line in lines if line]


def _assemble(meta_title: str, paragraphs: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        # OCF: mimetype 는 첫 엔트리 + 무압축.
        mimetype_info = zipfile.ZipInfo('mimetype')
        mimetype_info.compress_type = zipfile.ZIP_STORED
        archive.writestr(mimetype_info, MIMETYPE)

        archive.writestr('version.xml', _version_xml())
        archive.writestr('settings.xml', _settings_xml())
        archive.writestr('Contents/content.hpf', _content_hpf(meta_title))
        archive.writestr('Contents/header.xml', _header_xml())
        archive.writestr('Contents/section0.xml', _section_xml(paragraphs))
        archive.writestr('META-INF/container.xml', _container_xml())
        archive.writestr('META-INF/manifest.xml', _manifest_xml())

    return buffer.getvalue()


def build_hwpx(title: str, body: str) -> bytes:
    """제목 + 본문을 최소 OWPML .hwpx(ZIP 바이트)로 조립한다.

    제목이 첫 문단(머리)로 들어가고 본문 문단이 뒤따른다. mimetype 은 첫 엔트리 + 무압축(OCF).
    """

    title = (title or '무제').strip() or '무제'
    return _assemble(title, [title, *split_paragraphs(body)])


def build_hwpx_document(title: str, paragraphs: list[str]) -> bytes:
    """이미 양식별로 구조화된 문단 리스트를 그대로 .hwpx 로 조립한다(첫 문단이 머리).

    ``title`` 은 패키지 메타데이터/파일명용이며, 본문은 ``paragraphs`` 가 진실 원천이다.
    """

    title = (title or '무제').strip() or '무제'
    cleaned = [p for p in paragraphs if p and p.strip()]
    return _assemble(title, cleaned or [title])
