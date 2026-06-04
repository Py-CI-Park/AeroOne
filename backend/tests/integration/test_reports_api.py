from __future__ import annotations


def test_civil_aircraft_report_returns_sanitized_html(client, test_paths) -> None:
    (test_paths['civil_aircraft_root'] / '상용항공기_종합스펙_v2.0.html').write_text(
        '<html><head><title>민간 항공기</title>'
        '<link rel="stylesheet" href="https://cdn.example.com/x.css"></head>'
        '<body><script>window.__report=1</script>'
        '<img src="https://cdn.example.com/a.png"/>'
        '<img src="local.png"/></body></html>',
        encoding='utf-8',
    )

    response = client.get('/api/v1/reports/civil-aircraft/content/html')

    assert response.status_code == 200
    payload = response.json()
    assert payload['asset_type'] == 'html'
    html = payload['content_html']
    # 인라인 스크립트는 보존(보고서 본문 주입 JS 가 그대로 동작해야 함).
    assert 'window.__report=1' in html
    # 외부 <link>(폰트/스타일)와 외부 절대 src 는 차단(폐쇄망 외부 요청 방지).
    assert 'cdn.example.com/x.css' not in html
    assert 'https://cdn.example.com/a.png' not in html
    # 상대 경로 리소스는 보존.
    assert 'local.png' in html
    # 뉴스레터 HTML 과 동일한 CSP 헤더.
    assert response.headers.get('content-security-policy')


def test_civil_aircraft_report_skips_debug_and_404_when_only_debug(client, test_paths) -> None:
    # _debug.html 만 있으면 newsletter 와 같은 정책으로 제외 → 보고서 없음(404).
    (test_paths['civil_aircraft_root'] / 'report_debug.html').write_text('<html>debug</html>', encoding='utf-8')

    response = client.get('/api/v1/reports/civil-aircraft/content/html')

    assert response.status_code == 404


def test_civil_aircraft_report_404_when_missing(client) -> None:
    # 빈 _database/civil_aircraft 디렉토리(conftest 기본) → 보고서 없음.
    response = client.get('/api/v1/reports/civil-aircraft/content/html')

    assert response.status_code == 404
