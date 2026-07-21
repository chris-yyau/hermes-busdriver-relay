#!/bin/bash -p
#
# Required-check drift detector. Verifies .github/required-checks.lock against:
#   (a) workflow source   — each required entry maps to its declared job, and
#                           the required name is the job's own key or `name:`
#                           (scoped to the job block — not any name: in the file)
#   (b) branch protection — lock's `(required name, app_id)` set exactly equals
#                           the server's app-bound contexts set
#
# `source_app` is descriptive; numeric `app_id` is the reporter authority used
# in the remote comparison. Global job-name uniqueness is omitted because it
# needs a real YAML parser to distinguish job names from `on:`/step keys. The
# local check still requires every declared job key and its effective name.
#
# Exit: 0 = clean, 1 = drift, 2 = config error.
#
#   ./scripts/check-required-checks.sh --owner X --repo Y  # (a)+(b)
#   ./scripts/check-required-checks.sh --local-only    # (a) only, no API
#   ./scripts/check-required-checks.sh --owner X --repo Y
set -uo pipefail
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

# Resolve credential-capable tools from frozen sources only.  The validator walks root-owned,
# non-writable ancestry, opens the leaf without following symlinks, checks metadata and digest,
# and re-proves descriptor and pathname identity after hashing.  It runs before any gh command,
# so a rejected gh can never inherit GitHub credentials.
credential_free_exec() (
  local environment_name
  while IFS= read -r environment_name; do
    unset "$environment_name"
  done < <(compgen -e)
  PATH=/usr/bin:/bin:/usr/sbin:/sbin
  LC_ALL=C
  export PATH LC_ALL
  "$@"
)

# GitHub network calls receive only explicit token credentials. In particular, GH_HOST/GH_REPO,
# proxy variables, language/shell loaders and Git configuration never cross this boundary.
credential_bearing_exec() (
  local saved_gh_token="${GH_TOKEN-}"
  local saved_github_token="${GITHUB_TOKEN-}"
  local saved_ghe_token="${GH_ENTERPRISE_TOKEN-}"
  local saved_github_enterprise_token="${GITHUB_ENTERPRISE_TOKEN-}"
  local environment_name
  while IFS= read -r environment_name; do
    unset "$environment_name"
  done < <(compgen -e)
  PATH=/usr/bin:/bin:/usr/sbin:/sbin
  LC_ALL=C
  export PATH LC_ALL
  [[ -z "$saved_gh_token" ]] || { GH_TOKEN="$saved_gh_token"; export GH_TOKEN; }
  [[ -z "$saved_github_token" ]] || { GITHUB_TOKEN="$saved_github_token"; export GITHUB_TOKEN; }
  [[ -z "$saved_ghe_token" ]] || { GH_ENTERPRISE_TOKEN="$saved_ghe_token"; export GH_ENTERPRISE_TOKEN; }
  [[ -z "$saved_github_enterprise_token" ]] || {
    GITHUB_ENTERPRISE_TOKEN="$saved_github_enterprise_token"; export GITHUB_ENTERPRISE_TOKEN;
  }
  "$@"
)

# Emit at most limit+1 bytes, so callers can distinguish exact-bound success from overflow while
# command substitution itself remains bounded. pipefail propagates gh failure or SIGPIPE overflow.
bounded_credential_capture() (
  local limit="$1"
  shift
  set -o pipefail
  credential_bearing_exec "$@" | /usr/bin/head -c "$((limit + 1))"
)

# Capture both streams through bounded pipes before either reaches a regular file.  Closing the
# capture pipe bounds even a credential-bearing producer that ignores ordinary response sizes.
bounded_credential_request() (
  local stdout_limit="$1" stderr_limit="$2" stdout_path="$3" stderr_path="$4"
  shift 4
  local command_rc stdout_pid stderr_pid stdout_data stderr_data
  exec 3> >(/usr/bin/head -c "$((stderr_limit + 1))" >"$stderr_path")
  stderr_pid=$!
  exec 4> >(/usr/bin/head -c "$((stdout_limit + 1))" >"$stdout_path")
  stdout_pid=$!
  credential_bearing_exec "$@" >&4 2>&3
  command_rc=$?
  exec 3>&- 4>&-
  wait "$stdout_pid" || command_rc=125
  wait "$stderr_pid" || command_rc=125
  stdout_data=$(<"$stdout_path")
  stderr_data=$(<"$stderr_path")
  if [[ ${#stdout_data} -gt "$stdout_limit" || ${#stderr_data} -gt "$stderr_limit" ]]; then
    return 125
  fi
  return "$command_rc"
)

PROTECTION_INVENTORY_JQ='(.checks // []) as $checks | [((.contexts // [])[] as $context | select(any($checks[]; .context == $context) | not) | {context:$context, app_id:null}), ($checks[] | {context:.context, app_id:(.app_id // null)})] | unique_by([.context, .app_id]) | sort_by(.context, .app_id)'
LOCK_INVENTORY_JQ='[.required[] | {context:.name, app_id:(.app_id // null)}] | unique_by([.context, .app_id]) | sort_by(.context, .app_id)'

trusted_tool() {
  # /usr/bin/python3 is Apple's developer-tool multi-call shim.  Scrubbing after it
  # starts is too late: redirect variables can make the shim execute attacker bytes.
  # Build its environment from nothing using Bash builtins, before the kernel launch.
  # The caller's environment remains available only for an already-validated gh.
  credential_free_exec /usr/bin/python3 -I -c '
import hashlib, os, stat, sys
path, expected, name = sys.argv[1:]
def fail(reason):
    print("trusted_runtime_rejected:" + name + ":" + reason, file=sys.stderr); raise SystemExit(2)
if not path.startswith("/"): fail("not_absolute")
parts = path.split("/")[1:]; fd = os.open("/", os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
try:
    st=os.fstat(fd)
    if st.st_uid or st.st_mode & 0o022: fail("ancestry_untrusted")
    for part in parts[:-1]:
        nxt=os.open(part, os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW, dir_fd=fd); os.close(fd); fd=nxt
        st=os.fstat(fd)
        if st.st_uid or st.st_mode & 0o022: fail("ancestry_untrusted")
    try: leaf=os.open(parts[-1], os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW, dir_fd=fd)
    except FileNotFoundError: fail("unavailable")
    except OSError: fail("open_failed")
    try:
        opened=os.fstat(leaf)
        if not stat.S_ISREG(opened.st_mode) or opened.st_uid or opened.st_mode & 0o022 or not opened.st_mode & 0o111: fail("metadata_invalid")
        if opened.st_nlink != 1: fail("multiply_linked")
        digest=hashlib.sha256()
        while True:
            chunk=os.read(leaf, 1024*1024)
            if not chunk: break
            digest.update(chunk)
        if digest.hexdigest() != expected: fail("integrity_failed")
        closing=os.fstat(leaf); named=os.lstat(parts[-1], dir_fd=fd)
        identity=lambda s:(s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if identity(closing) != identity(opened) or (named.st_dev,named.st_ino)!=(opened.st_dev,opened.st_ino): fail("identity_changed")
    finally: os.close(leaf)
finally: os.close(fd)
print(path)
' "$1" "$2" "$3"
}

JQ=$(trusted_tool /usr/bin/jq 49356fcef7adb7afdb76c9e258eef0e78df3673ba0fb4d479905432c117f579a jq) || exit 2

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

if [[ "$LOCAL_ONLY" -eq 0 ]]; then
  if [[ -z "$OWNER" || -z "$REPO" ]]; then
    echo "config error: remote validation requires both --owner and --repo" >&2
    exit 2
  fi
fi

[[ -f "$LOCK" ]] || { echo "config error: $LOCK not found" >&2; exit 2; }
credential_free_exec "$JQ" empty "$LOCK" 2>/dev/null || { echo "config error: $LOCK is not valid JSON" >&2; exit 2; }

drift=0

# For a `  <job>:` key (2-space indent under top-level `jobs:`), echo whether
# the job exists ("EXISTS"/"") and, on its own line, the value of the job's
# DIRECT `name:` child (the field at exactly base+2 indent — NOT a nested
# step `- name:` or a `with: { name: }`). Output: line 1 = "1" if job found
# else "0"; line 2 = the job's own name value (empty if none). Comparison of
# the name is done as an exact string by the caller (no regex), so a required
# check name containing regex metacharacters is handled literally.
job_name() {
  credential_free_exec /usr/bin/awk -v job="$1" '
    function indent(s,   i){ i=match(s, /[^ ]/); return (i==0)? 9999 : i-1 }
    { line=$0; sub(/[[:space:]]+$/, "", line) }
    line == "  " job ":" { found=1; inblk=1; base=indent($0); next }
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
  if [[ ! "$job" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    echo "DRIFT (a): invalid literal job key '$job' for required '$name'"; drift=1; continue
  fi
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
done < <(credential_free_exec "$JQ" -r '.required[] | select(.source_app=="github-actions") | [.name, .job, .workflow] | @tsv' "$LOCK" || true)

# ── (b) lock vs branch protection ──
if [[ "$LOCAL_ONLY" -eq 0 ]]; then
  GH=$(trusted_tool /usr/local/bin/gh 02d2d4a85241c6a8c0b77ebb1ec76fc723caf7fb128e00915b306b968847cba1 gh) || {
    echo "DRIFT (b): trusted gh unavailable; reason=trusted_root_owned_gh_unavailable"; exit 2;
  }
      DEFAULT_BRANCH=$(bounded_credential_capture 4096 "$GH" api "repos/$OWNER/$REPO" --jq .default_branch 2>/dev/null) || DEFAULT_BRANCH=""
      [[ ${#DEFAULT_BRANCH} -le 4096 ]] || DEFAULT_BRANCH=""
      if [[ -z "$DEFAULT_BRANCH" ]]; then
        # Fail-CLOSED: an empty default branch means the repo lookup failed
        # (auth/network/API). Do NOT proceed — a query with an empty branch
        # would 404 and be misread below as "no protection". Flag drift.
        echo "DRIFT (b): could not resolve default branch (gh api error)"; drift=1
      else
      out=$(/usr/bin/mktemp)
      err=$(/usr/bin/mktemp)
      bounded_credential_request 65536 4096 "$out" "$err" "$GH" api "repos/$OWNER/$REPO/branches/$DEFAULT_BRANCH/protection/required_status_checks"
      rc=$?
      raw=$(<"$out")
      error_text=$(<"$err")
      if [[ ${#raw} -gt 65536 ]]; then
        rc=125
        /usr/bin/printf '%s\n' 'response_too_large' >"$err"
      elif [[ ${#error_text} -gt 4096 ]]; then
        rc=125
        /usr/bin/printf '%s\n' 'stderr_too_large' >"$err"
      fi
      /bin/rm -f "$out"
      if [[ $rc -ne 0 ]]; then
        # Fail-CLOSED: only a genuine 404 (no protection / no required checks)
        # is a legitimate skip. Auth, network, or other API errors must NOT be
        # silently treated as "clean" — flag them as drift.
        if /usr/bin/grep -qiE 'HTTP 404|Not Found' "$err"; then
          want=$("$JQ" -c "$LOCK_INVENTORY_JQ" "$LOCK")
          if [[ "$want" == "[]" ]]; then
            echo "(b) branch protection absent and lock requires no checks"
          else
            echo "DRIFT (b): branch protection absent but lock requires checks"
            drift=1
          fi
        else
          echo "DRIFT (b): gh api error querying branch protection: $( { /usr/bin/tr -d '\r' < "$err" | /usr/bin/head -c 200; } || true)"
          drift=1
        fi
        /bin/rm -f "$err"
      else
        /bin/rm -f "$err"
        have=$(/usr/bin/printf '%s' "$raw" | "$JQ" -c "$PROTECTION_INVENTORY_JQ" 2>/dev/null) || have=""
        if [[ -z "$have" ]]; then
          echo "DRIFT (b): branch-protection response had no contexts array"; drift=1
        else
          want=$("$JQ" -c "$LOCK_INVENTORY_JQ" "$LOCK")
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
