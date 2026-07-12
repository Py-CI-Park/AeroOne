#!/usr/bin/env bash

set -euo pipefail

readonly REPOSITORY="Py-CI-Park/AeroOne"
readonly APPROVAL_TOKEN="APPROVE-EXACT-HISTORICAL-ASSET-DELETION"
readonly WARNING=$'> [!WARNING]\r\n> 이 릴리스의 오프라인 ZIP 자산은 패키징 안전성 문제로 회수되었습니다. 사용하거나 재배포하지 마십시오. 교체 릴리스 1.12.3을 준비 중입니다.\r\n\r\n'
readonly CONTRACTS=$'1.12.1|468959744|sha256:9b42988bed4344b83f8691b0e297f9489d0a861e6ac35fb8b6c92be2d26648f2|468959745|sha256:89821736f134c9b432b8d98af324b14430f5f8c54d3d5b3da329413ffab557a1\n1.12.0|467598771|sha256:01608c2f4fa039e8cf1cbdcd82f9995dbb1173e52f2898248d02ae64b8f4cb52|467598772|sha256:91f08a868288456b87f7c44d497de6691873fa9883788453e4af7090c8cc00b1\n1.11.0|467141283|sha256:c8435df405b1a84158874965e7e36525a3dfc31a9c0b0cf7cf37bd453c0db942|467141282|sha256:be43aaafa0c19c7c60ab4fc7c2d5c26d8bdb09c64fa731059855f0ab72437879\n1.10.0|466204038|sha256:5bfd1e8dd141f505b169afbb4f6e7114f337248e48ab80c3b8c91684b3916ad3|466204039|sha256:02fb5bba263f66cf95abdae76ef6dc0d4f79f1dc7777c9c31d42814f40cdeea4\n1.8.0|465087963|sha256:8abea7926e0c5b8836868ec9a2ecf774a610ed5c87d96e2efa4187aa08b10ceb|465087964|sha256:e6897ded0a0f5dc8892c6fd30b81f89610d00bd3e7a1ce18f0b02c123f186e7c\n1.7.1|463971385|sha256:492d99335b5b4a939a86d07e89757e5840ce2f52ba7cddcbb44ede506ea033ca|463971384|sha256:006064483b713cd12125ab8afdaf3d76db582dd992c1dde5c3b9ece9221a6531\n1.7.0|460314227|sha256:df9d9d7bc3ed9b98561e3cd6a898b9cbcd29a5e28c50934c6ad8ff8b8e11189d|460314229|sha256:044f7bfe7efda686934ee0f5e2d132f51d9ede7be442252e037197339ccdd15b\n1.7.0|460314230|sha256:028f0d2f9a9f0563df36dbe121a57581057dd63966c97808e6c97dbf5b22ae07|460314228|sha256:d97e365eddb4a8c0fcc82e905194453f1065f92052375ed582e037a2927f7d70\n1.6.2|451005119|sha256:246fad2df15770f3a36dfa3866f0866bc48e60b18253a1da9ff809f4c588cbe9|451005118|sha256:5493c7d2f4bd23724904527f5c6f7c699db8e60289c0df5c5d943b6f71685335\n1.6.1|449183210|sha256:c28c4d431e587d3df252984a1a4c8012f5301aee08a4ef230e049fca8f225f9f|449183209|sha256:97e9e60f8242772bf06ba6b87b47b628ca98309b4619fbd19a5035f0047d50ea\n1.6.0|448898337|sha256:60b162581e53dbba5c155c1e5ea7b794741d7efe65e2999dafa1a5cbf038fc00|448898338|sha256:49650d0182affe374b5d53b8e031581b39de238fbc3e20cbd72bdf2b64c67144\n1.5.0|448050524|sha256:9a057cf34de86ab220202b3b215baff32c5f5a1617ea55e33bcc8d575d55c6ec|448050525|sha256:7f92655d8afa9f1d6f9faf7e9d85e5dcc09800dfd5d0bd04fbd656e60e33e114\n1.5.0|448050213|sha256:faa0887c710a76af3df579ba41e35bcf7c9f23d57fd117177af280126ea8eebe|448050212|sha256:66ac8dc080f6a18562a291c01c843b9d4c1dcdc219127b0c444a12905e0671a9\n1.4.4|445483030|sha256:2d9da5e8188ec1d93736e1a2c5c4e977b5fef86a32cb8da728f59fb9c387bfd2|445483029|sha256:baf72bbefacda00e147199e7935ef2001f0942ae2a32c53311cc7e9d449142d1'

mode="dry-run"
approval_token=""

usage() {
  printf '%s\n' \
    'Usage:' \
    '  task-2-contain-historical-assets.sh' \
    '  task-2-contain-historical-assets.sh --execute --approval-token TOKEN' \
    '' \
    'Default mode is read-only dry-run. Execute mode requires the exact approval token' \
    'printed after the owner explicitly approves all 14 ZIP/SHA pairs.'
}

while (($# > 0)); do
  case "$1" in
    --execute)
      mode="execute"
      shift
      ;;
    --approval-token)
      if (($# < 2)); then
        printf 'error=missing_approval_token_value\n' >&2
        exit 64
      fi
      approval_token="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'error=unknown_argument argument=%s\n' "$1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if [[ "$mode" == "execute" && "$approval_token" != "$APPROVAL_TOKEN" ]]; then
  printf 'error=explicit_owner_approval_required\n' >&2
  exit 64
fi

if [[ "$mode" == "dry-run" && -n "$approval_token" ]]; then
  printf 'error=approval_token_requires_execute_mode\n' >&2
  exit 64
fi

command -v gh >/dev/null
command -v jq >/dev/null
command -v curl >/dev/null
command -v sha256sum >/dev/null
gh auth status -h github.com >/dev/null

mapfile -t tags < <(printf '%s\n' "$CONTRACTS" | cut -d'|' -f1 | awk '!seen[$0]++')

validated_pairs=0
validated_assets=0
mutated_releases=0

for tag in "${tags[@]}"; do
  mapfile -t rows < <(printf '%s\n' "$CONTRACTS" | awk -F'|' -v tag="$tag" '$1 == tag')
  release="$(gh api "repos/$REPOSITORY/releases/tags/$tag")"

  release_id="$(printf '%s' "$release" | jq -r '.id')"
  tag_commit_before="$(gh api "repos/$REPOSITORY/commits/$tag" --jq '.sha')"
  draft_before="$(printf '%s' "$release" | jq -r '.draft')"
  prerelease_before="$(printf '%s' "$release" | jq -r '.prerelease')"
  warning_present="$(printf '%s' "$release" | jq -r --arg warning "$WARNING" '.body | startswith($warning)')"

  if [[ "$warning_present" == "true" ]]; then
    original_body_sha="$(printf '%s' "$release" | jq -j --arg warning "$WARNING" '.body[($warning | length):]' | sha256sum | awk '{print $1}')"
    original_body_normalized_sha="$(printf '%s' "$release" | jq -j --arg warning "$WARNING" '.body[($warning | length):]' | tr -d '\r' | sha256sum | awk '{print $1}')"
  else
    original_body_sha="$(printf '%s' "$release" | jq -j '.body' | sha256sum | awk '{print $1}')"
    original_body_normalized_sha="$(printf '%s' "$release" | jq -j '.body' | tr -d '\r' | sha256sum | awk '{print $1}')"
  fi

  target_ids=()
  target_urls=()

  for row in "${rows[@]}"; do
    IFS='|' read -r row_tag zip_id zip_digest sha_id sha_digest <<<"$row"
    test "$row_tag" = "$tag"

    zip_count="$(printf '%s' "$release" | jq -r --argjson id "$zip_id" '[.assets[] | select(.id == $id)] | length')"
    sha_count="$(printf '%s' "$release" | jq -r --argjson id "$sha_id" '[.assets[] | select(.id == $id)] | length')"
    test "$zip_count" = "1"
    test "$sha_count" = "1"

    actual_zip_digest="$(printf '%s' "$release" | jq -r --argjson id "$zip_id" '.assets[] | select(.id == $id) | .digest')"
    actual_sha_digest="$(printf '%s' "$release" | jq -r --argjson id "$sha_id" '.assets[] | select(.id == $id) | .digest')"
    actual_zip_name="$(printf '%s' "$release" | jq -r --argjson id "$zip_id" '.assets[] | select(.id == $id) | .name')"
    actual_sha_name="$(printf '%s' "$release" | jq -r --argjson id "$sha_id" '.assets[] | select(.id == $id) | .name')"

    test "$actual_zip_digest" = "$zip_digest"
    test "$actual_sha_digest" = "$sha_digest"
    [[ "$actual_zip_name" == *.zip ]]
    test "$actual_sha_name" = "$actual_zip_name.sha256"

    target_ids+=("$zip_id" "$sha_id")
    target_urls+=(
      "$(printf '%s' "$release" | jq -r --argjson id "$zip_id" '.assets[] | select(.id == $id) | .browser_download_url')"
      "$(printf '%s' "$release" | jq -r --argjson id "$sha_id" '.assets[] | select(.id == $id) | .browser_download_url')"
    )
    ((validated_pairs += 1))
    ((validated_assets += 2))
  done

  target_json="$(printf '%s\n' "${target_ids[@]}" | jq -Rsc 'split("\n")[:-1] | map(tonumber)')"
  other_assets_before="$(printf '%s' "$release" | jq -cS --argjson targets "$target_json" '[.assets[] | select(.id as $id | ($targets | index($id) | not)) | {id,name,size,digest,browser_download_url}]')"
  other_assets_before_sha="$(printf '%s' "$other_assets_before" | sha256sum | awk '{print $1}')"

  printf 'mode=%s tag=%s release_id=%s pair_count=%s warning_present=%s body_sha256=%s body_normalized_sha256=%s other_assets_sha256=%s\n' \
    "$mode" "$tag" "$release_id" "${#rows[@]}" "$warning_present" "$original_body_sha" "$original_body_normalized_sha" "$other_assets_before_sha"

  if [[ "$mode" == "dry-run" ]]; then
    continue
  fi

  payload="$(printf '%s' "$release" | jq -c --arg warning "$WARNING" '{body: (if (.body | startswith($warning)) then .body else ($warning + .body) end)}')"
  printf '%s' "$payload" | gh api --method PATCH "repos/$REPOSITORY/releases/$release_id" --input - >/dev/null

  for target_id in "${target_ids[@]}"; do
    gh api --method DELETE "repos/$REPOSITORY/releases/assets/$target_id" >/dev/null
  done

  after="$(gh api "repos/$REPOSITORY/releases/$release_id")"
  test "$(printf '%s' "$after" | jq -r '.id')" = "$release_id"
  test "$(printf '%s' "$after" | jq -r '.tag_name')" = "$tag"
  test "$(printf '%s' "$after" | jq -r '.draft')" = "$draft_before"
  test "$(printf '%s' "$after" | jq -r '.prerelease')" = "$prerelease_before"
  test "$(gh api "repos/$REPOSITORY/commits/$tag" --jq '.sha')" = "$tag_commit_before"
  test "$(printf '%s' "$after" | jq -r --arg warning "$WARNING" '.body | startswith($warning)')" = "true"

  suffix_sha="$(printf '%s' "$after" | jq -j --arg warning "$WARNING" '.body[($warning | length):]' | sha256sum | awk '{print $1}')"
  suffix_normalized_sha="$(printf '%s' "$after" | jq -j --arg warning "$WARNING" '.body[($warning | length):]' | tr -d '\r' | sha256sum | awk '{print $1}')"
  test "$suffix_sha" = "$original_body_sha"
  test "$suffix_normalized_sha" = "$original_body_normalized_sha"

  target_count_after="$(printf '%s' "$after" | jq -r --argjson targets "$target_json" '[.assets[] | select(.id as $id | ($targets | index($id)))] | length')"
  test "$target_count_after" = "0"
  other_assets_after="$(printf '%s' "$after" | jq -cS '[.assets[] | {id,name,size,digest,browser_download_url}]')"
  test "$(printf '%s' "$other_assets_after" | sha256sum | awk '{print $1}')" = "$other_assets_before_sha"

  for target_url in "${target_urls[@]}"; do
    status="$(curl --max-time 30 -L -sS -o /dev/null -w '%{http_code}' "$target_url")"
    test "$status" = "404"
  done

  ((mutated_releases += 1))
  printf 'contained=true tag=%s release_id=%s target_assets=%s old_urls_404=%s\n' \
    "$tag" "$release_id" "${#target_ids[@]}" "${#target_urls[@]}"
done

test "$validated_pairs" = "14"
test "$validated_assets" = "28"

printf 'summary mode=%s releases=%s pairs=%s assets=%s mutated_releases=%s validated=true\n' \
  "$mode" "${#tags[@]}" "$validated_pairs" "$validated_assets" "$mutated_releases"

if [[ "$mode" == "dry-run" ]]; then
  printf 'execute_approval_token=%s\n' "$APPROVAL_TOKEN"
fi
