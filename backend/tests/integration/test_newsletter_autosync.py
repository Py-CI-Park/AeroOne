def test_calendar_reflects_new_output_file_without_admin_sync(client, settings) -> None:
    # 베이스라인: 최초 조회가 기존 output(20260206)을 자동 동기화한다(관리자 Sync 없이).
    baseline = client.get('/api/v1/newsletters/calendar')
    assert baseline.status_code == 200
    baseline_slugs = {entry['slug'] for entry in baseline.json()}
    assert 'newsletter-20260206' in baseline_slugs
    assert 'newsletter-20260207' not in baseline_slugs

    # 운영자가 새 발행호 HTML 을 output 에 추가 — 서버 재시작도 관리자 Sync 도 없다.
    (settings.import_root / 'newsletter_20260207.html').write_text(
        '<html><head><title>20260207 발행호</title></head><body><p>본문</p></body></html>',
        encoding='utf-8',
    )

    # 다음 공개 읽기 요청에서 폴더 변경이 감지되어 새 발행호가 달력에 등장한다.
    after = client.get('/api/v1/newsletters/calendar')
    assert after.status_code == 200
    after_slugs = {entry['slug'] for entry in after.json()}
    assert 'newsletter-20260207' in after_slugs
    assert 'newsletter-20260206' in after_slugs


def test_latest_switches_to_newer_output_file_on_read(client, settings) -> None:
    client.get('/api/v1/newsletters/latest')  # baseline (20260206)

    (settings.import_root / 'newsletter_20260301.html').write_text(
        '<html><head><title>20260301 발행호</title></head><body><p>최신</p></body></html>',
        encoding='utf-8',
    )

    response = client.get('/api/v1/newsletters/latest')
    assert response.status_code == 200
    assert response.json()['slug'] == 'newsletter-20260301'
