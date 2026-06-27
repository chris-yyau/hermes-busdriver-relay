#!/usr/bin/env bash
#
# Required-check drift detector. Verifies .github/required-checks.lock against:
#   (a) workflow source   — each required entry maps to its declared job, and
#                           the required name is the job's own key or `name:`
#                           (scoped to the job block — not any name: in the file)
#   (b) branch protection — lock's required-name set == server's contexts set
#
# (c) reporter-app verification and (d) global name-uniqueness are omitted in
# this lean version. (c) adds little signal for an all-`github-actions` lock;
# (d) needs a real YAML parser to distinguish job names from `on:`/step keys
# (no stdlib YAML here). ponytail: add (c)/(d) (via a YAML lib) if this repo
# grows external required checks or many workflows.
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
    # Guard the value before `$2` so a trailing `--owner`/`--repo` with no
    # argument exits 2 (config error) instead of crashing under `set -u`.
    --owner) [[ $# -ge 2 ]] || { echo "config error: --owner needs a value" >&2; exit 2; }; OWNER="$2"; shift 2 ;;
    --repo)  [[ $# -ge 2 ]] || { echo "config error: --repo needs a value"  >&2; exit 2; }; REPO="$2";  shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$LOCK" ]] || { echo "config error: $LOCK not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "config error: jq required" >&2; exit 2; }
jq empty "$LOCK" 2>/dev/null || { echo "config error: $LOCK is not valid JSON" >&2; exit 2; }

drift=0

# For a `  <job>:` key (2-space indent under top-level `jobs:`), echo whether
# the job exists ("EXISTS"/"") and, on its own line, the value of the job's
# DIRECT `name:` child (the field at exactly base+2 indent — NOT a nested
# step `- name:` or a `with: { name: }`). Output: line 1 = "1" if job found
# else "0"; line 2 = the job's own name value (empty if none). Comparison of
# the name is done as an exact string by the caller (no regex), so a required
# check name containing regex metacharacters is handled literally.
job_name() {
  awk -v job="$1" '
    function indent(s,   i){ i=match(s, /[^ ]/); return (i==0)? 9999 : i-1 }
    $0 ~ "^  " job ":[[:space:]]*$" { found=1; inblk=1; base=indent($0); next }
    inblk && $0 !~ /^[[:space:]]*$/ && indent($0) <= base { inblk=0 }
    inblk && !gotname && indent($0)==base+2 && $0 ~ /^[[:space:]]+name:[[:space:]]/ {
      v=$0; sub(/^[[:space:]]+name:[[:space:]]*/,"",v); sub(/[[:space:]]+$/,"",v)
      sub(/^"/,"",v); sub(/"$/,"",v); sub(/^'\''/,"",v); sub(/'\''$/,"",v)
      name=v; gotname=1
    }
    END { print (found?1:0); print name }
  ' "$2"
}

# ── (a) lock vs workflow source ──
while IFS=$'\t' read -r name job wf; do
  [[ -n "$wf" ]] || continue
  if [[ ! -f "$wf" ]]; then
    echo "DRIFT (a): $wf missing for required check '$name'"; drift=1; continue
  fi
  { IFS= read -r found; IFS= read -r actual_name; } < <(job_name "$job" "$wf" || true)
  if [[ "$found" != "1" ]]; then
    echo "DRIFT (a): job key '$job' not found in $wf (required '$name')"; drift=1; continue
  fi
  # The effective check name GitHub reports is the job's own `name:` if present,
  # else the job key — accept ONLY that. Accepting the job id when a `name:`
  # exists would pass a lock entry branch protection can never satisfy (GitHub
  # reports the name, not the id). Exact string compare (no regex).
  effective="${actual_name:-$job}"
  if [[ "$name" != "$effective" ]]; then
    echo "DRIFT (a): required name '$name' is not the effective check name '$effective' for job '$job' in $wf"; drift=1
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
      if [[ -z "$DEFAULT_BRANCH" ]]; then
        # Fail-CLOSED: an empty default branch means the repo lookup failed
        # (auth/network/API). Do NOT proceed — a query with an empty branch
        # would 404 and be misread below as "no protection". Flag drift.
        echo "DRIFT (b): could not resolve default branch (gh api error)"; drift=1
      else
      err=$(mktemp)
      raw=$(gh api "repos/$OWNER/$REPO/branches/$DEFAULT_BRANCH/protection/required_status_checks" 2>"$err"); rc=$?
      if [[ $rc -ne 0 ]]; then
        # Fail-CLOSED: only a genuine 404 (no protection / no required checks)
        # is a legitimate skip. Auth, network, or other API errors must NOT be
        # silently treated as "clean" — flag them as drift.
        if grep -qiE 'HTTP 404|Not Found' "$err"; then
          echo "skip (b): no branch protection / required checks on $DEFAULT_BRANCH yet"
        else
          echo "DRIFT (b): gh api error querying branch protection: $( { tr -d '\r' < "$err" | head -c 200; } || true)"
          drift=1
        fi
        rm -f "$err"
      else
        rm -f "$err"
        have=$(printf '%s' "$raw" | jq -c 'if (.contexts|type=="array") then (.contexts|sort) else empty end' 2>/dev/null) || have=""
        if [[ -z "$have" ]]; then
          echo "DRIFT (b): branch-protection response had no contexts array"; drift=1
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
  fi
fi

[[ "$drift" -eq 0 ]] && echo "required-checks: clean"
exit "$drift"
