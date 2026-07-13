# Task 2 독립 최종 판정

- 판정: `AdversarialVerify: confirmed`
- 범위: 승인된 historical ZIP/SHA 14쌍(28 asset)의 정확 삭제, 12개 release 경고 추가, 기존 release/tag/body suffix/비대상 asset 보존
- 외부 쓰기: 없음

## 독립 확인

1. 실행 증적의 실행기 SHA-256 `e5df09b26be329ad13b3b34560cda990130e19c410df580d42378980bf2d3221`은 현재 `.omo/evidence/v1-13-0/task-2-contain-historical-assets.sh`의 독립 계산값과 일치했다.
2. 실행기는 `set -euo pipefail`과 exact approval token guard를 사용한다. 각 대상은 삭제 전에 release 내 ID 단일성, digest, ZIP/SHA 이름 짝을 확인하고, 삭제 뒤에는 target ID 부재, release ID/tag/draft/prerelease/tag commit 보존, warning 존재, 원문 body suffix의 raw/LF-normalized SHA-256 보존, 비대상 asset 집합 SHA-256 보존, 실행 중 메모리에 잡은 old browser URL의 HTTP 404를 모두 assertion한다. 하나라도 실패하면 최종 성공 summary에 도달할 수 없다.
3. 실행 증적은 exit `0`, `releases=12 pairs=14 assets=28 mutated_releases=12 validated=true`, target 삭제 `28/28`, old URL `28/28 = 404`, suffix·메타데이터·비대상 asset 보존 `12/12`를 기록한다. release별 before/after hash도 계약 문서의 pre-delete hash와 일치한다.
4. 독립 live API 표본에서 전체 release 수 `46`을 확인했고, `1.12.1`, `1.12.0`, `1.11.0`, `1.10.0`은 각각 release ID, warning prefix, raw/LF-normalized suffix hash, 대상 asset ID 부재, 현재 asset 수 0, draft/prerelease=false가 증적과 일치했다. 첫 통합 검사에서 `1.10.0` 진입 시 무출력 assertion 종료가 있었으나, 같은 항목을 즉시 좁혀 재검사한 결과 모든 필드가 일치해 containment 불일치로 재현되지 않았다. 시간 제한에 따라 두 번째 전체 sweep은 중단했으며 긍정 증거로 계산하지 않았다.

## 증거 품질 한계

pre-delete 증적에는 28개의 `browser_download_url` 원문이 영속 기록되어 있지 않다. 따라서 제3자가 동일 URL 목록을 증적만으로 재구성해 404를 다시 실행할 수는 없다. 다만 실행기는 삭제 전에 API 응답에서 exact URL을 직접 수집하고 각 URL의 404를 검사한 뒤에만 exit 0과 최종 summary를 냈고, exact asset ID/digest 계약 및 삭제 후 ID 부재도 함께 검증했다. 이 한계는 삭제·보존 결과를 뒤집는 결함이 아니라 재현성에 관한 비차단 evidence-quality gap으로 분류한다.

후속 release containment에서는 삭제 전에 `{asset_id, browser_download_url}` 목록의 해시 또는 비밀이 아닌 URL 목록을 별도 증적에 남겨 독립 재실행성을 높이는 것이 바람직하다.

## 결론

현재 증거는 승인 범위를 벗어난 삭제 없이 exact 28 asset이 제거되고 12개 release의 보존 계약이 충족되었다고 판정하기에 충분하다. 위 URL 원문 미보존은 후속 증적 개선 항목이며 Task 2 완료를 막지 않는다.
