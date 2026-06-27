#!/usr/bin/env bash
# Verify every GitHub Actions `uses:` ref is pinned to a full 40-hex commit SHA.
# Matches BOTH the bare list-item form (`- uses: x@sha`) and the keyed form
# (`uses: x@sha`), and flags refs with no `@` at all (e.g. `uses: actions/foo`)
# — those are unpinned and must not slip through. Local (`./…`) and `docker://`
# refs are exempt.
set -euo pipefail
status=0
while IFS= read -r -d '' file; do
  while IFS= read -r raw; do
    line_no="${raw%%:*}"
    line="${raw#*:}"
    # Strip an optional leading `- ` list marker, the `uses:` key, any trailing
    # `# comment`, surrounding quotes, and anything after the first space.
    ref="$(printf '%s' "$line" \
      | sed -E "s/^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*//; s/[[:space:]]+#.*$//; s/[[:space:]].*$//; s/^['\"]//; s/['\"]$//")"
    case "$ref" in
      ''|./*|docker://*) continue ;;  # empty, local refs, and docker:// exempt
    esac
    if [[ ! "$ref" =~ ^[^@]+@[0-9a-f]{40}$ ]]; then
      echo "::error file=$file,line=$line_no::Unpinned or invalid action/workflow ref: $ref"
      status=1
    fi
  done < <(grep -nE '^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*[^[:space:]]+' "$file" || true)
done < <(find .github/workflows -type f \( -name '*.yml' -o -name '*.yaml' \) -print0 2>/dev/null || true; \
         find .github/actions  -type f \( -name '*.yml' -o -name '*.yaml' \) -print0 2>/dev/null || true)
exit "$status"
