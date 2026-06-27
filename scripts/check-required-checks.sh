#!/usr/bin/env bash
#
# Required-check drift detector. Verifies .github/required-checks.lock against:
#   (a) workflow source   — each required entry maps to its declared job
#   (b) branch protection — lock's required-name set == server's contexts set
#
# (c) reporter-app verification and (d) global name-uniqueness are omitted in
# this lean version. (c) adds little signal for an all-`github-actions` lock;
# (d) needs a real YAML parser to distinguish job names from `on:`/step keys
# (no stdlib YAML here) — with 5 workflows and distinct names it's review-
# enforced. ponytail: add (c)/(d) (via a YAML lib) if this repo grows external
# required checks or many workflows.
#
# Exit: 0 = clean, 1 = drift, 2 = config error.
#
#   ./scripts/check-required-checks.sh                 # (a)+(b)
#   ./scripts/check-required-checks.sh --local-only    # (a) only, no API
#   ./scripts/check-required-checks.sh --owner X --repo Y
set -uo pipefail

LOCK=".github/required-checks.lock"
LOCAL_ONLY=0
OWNER=""; REPO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --local-only) LOCAL_ONLY=1; shift ;;
    --owner) OWNER="$2"; shift 2 ;;
    --repo)  REPO="$2";  shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$LOCK" ]] || { echo "config error: $LOCK not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "config error: jq required" >&2; exit 2; }
jq empty "$LOCK" 2>/dev/null || { echo "config error: $LOCK is not valid JSON" >&2; exit 2; }

drift=0

# ── (a) lock vs workflow source ──
while IFS=$'\t' read -r name job wf; do
  [[ -n "$wf" ]] || continue
  if [[ ! -f "$wf" ]]; then
    echo "DRIFT (a): $wf missing for required check '$name'"; drift=1; continue
  fi
  # job key must exist; lock name must appear as the job key or a name: value.
  if ! grep -qE "^[[:space:]]+${job}:[[:space:]]*$" "$wf"; then
    echo "DRIFT (a): job key '$job' not found in $wf (required '$name')"; drift=1; continue
  fi
  if [[ "$name" != "$job" ]] && ! grep -qF "name: $name" "$wf"; then
    echo "DRIFT (a): required name '$name' not declared in $wf (job '$job')"; drift=1
  fi
done < <(jq -r '.required[] | select(.source_app=="github-actions") | [.name, .job, .workflow] | @tsv' "$LOCK" || true)

# ── (b) lock vs branch protection ──
if [[ "$LOCAL_ONLY" -eq 0 ]]; then
  if ! command -v gh >/dev/null; then
    echo "skip (b): gh not installed (use --local-only to silence)"
  else
    if [[ -z "$OWNER" || -z "$REPO" ]]; then
      nwo=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null) || nwo=""
      OWNER="${OWNER:-${nwo%%/*}}"; REPO="${REPO:-${nwo##*/}}"
    fi
    if [[ -z "$OWNER" || -z "$REPO" ]]; then
      echo "skip (b): could not resolve owner/repo"
    else
      DEFAULT_BRANCH=$(gh api "repos/$OWNER/$REPO" --jq .default_branch 2>/dev/null) || DEFAULT_BRANCH=""
      # Raw fetch — a missing protection returns a {"message":...} error object,
      # not an array. Only treat an actual array as server contexts.
      raw=$(gh api "repos/$OWNER/$REPO/branches/$DEFAULT_BRANCH/protection/required_status_checks" 2>/dev/null) || raw=""
      have=$(printf '%s' "$raw" | jq -c 'if type=="object" and (.contexts|type=="array") then (.contexts|sort) else empty end' 2>/dev/null) || have=""
      if [[ -z "$have" ]]; then
        echo "skip (b): no branch protection on $DEFAULT_BRANCH yet"
      else
        want=$(jq -c '[.required[].name] | sort' "$LOCK")
        if [[ "$want" != "$have" ]]; then
          echo "DRIFT (b): lock required != branch-protection contexts"
          echo "  lock:   $want"
          echo "  server: $have"
          drift=1
        else
          echo "(b) branch-protection contexts match lock"
        fi
      fi
    fi
  fi
fi

[[ "$drift" -eq 0 ]] && echo "required-checks: clean"
exit "$drift"
