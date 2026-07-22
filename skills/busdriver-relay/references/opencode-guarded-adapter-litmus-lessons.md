# OpenCode guarded adapter litmus lessons

Use these lessons when finishing or reviewing OpenCode fallback / comparison-lane work in `hermes-busdriver-relay`.

## What happened

During Delivery Mode dogfood on an OpenCode fallback adapter slice, commit-mode litmus initially failed after the diff was split into reviewable groups. The useful reviewer findings were not generic style issues; they exposed concrete contract gaps in the adapter surface.

## Durable lessons

1. **The OpenCode wrapper must fail closed when run outside `hermes-busdriver-agent-draft`.**
   - A standalone `scripts/opencode/run-opencode-busdriver-draft` call can bypass the parent launcher’s PATH guard, preflight, postflight, and lock semantics.
   - The wrapper should require a parent-provided proof such as `HERMES_AGENT_DRAFT_GUARDED=1` plus a `HERMES_AGENT_DRAFT_GUARD_BIN` that is first in `PATH` and contains executable `git` / `gh` guard shims.
   - If the guard proof is missing or malformed, write a blocked artifact and exit nonzero; do not launch OpenCode.

2. **Validator allowlists must match the committed schema.**
   - If `opencode-result.schema.json` allows fields such as `repo`, `artifacts`, `summary`, `changed_files`, `tests_run`, `review_findings`, `blocked_actions`, `limitations`, or `event_log`, the runtime validator must accept the same fields.
   - Conversely, if fail-closed paths write diagnostics such as `stdout_tail`, `stderr_tail`, `returncode`, `parse_error`, or `observed_result`, the schema must explicitly allow them with bounded types/lengths.
   - Contract drift between schema and validator should be covered by targeted tests, not left to reviewer discovery.

3. **Blocked artifacts require `ok: false`.**
   - `status == "blocked"` with `ok == true` is contradictory and must be rejected/re-written to a blocked fail-closed artifact.
   - Add a regression test for `blocked_requires_ok_false`.

4. **Nested authority objects require exact false-authority key sets.**
   - Checking that known authority flags are false is insufficient if extra nested keys like `dispatch_allowed: true` can be present.
   - Require `set(authority.keys()) == set(AUTHORITY_FALSE.keys())`, then require every root and nested authority flag to be false.
   - Add a regression test with an extra nested authority field and expect `authority_flags_invalid`.

5. **ADR/docs must not overclaim unavailable executor operations.**
   - If `hermes-busdriver-deliver` only exposes `plan`, `verify`, and `pr-grind`, ADRs/status docs must not claim `commit`, `push`, `pr-create`, `merge`, or `pr-grind-fix-loop` are implemented side-effect operations.
   - Either implement the operation with fresh evidence checks and tests, or downgrade the wording to “contract/design target” / “not yet exposed”.

6. **Oversized litmus diffs should be split, but every split gets its own fix loop.**
   - When commit-mode litmus exits `TOO_LARGE`, reset staging and create logical groups (adapter/schema/tests/docs, delivery executor, skill/docs, etc.).
   - For each group: stage only that group, run narrow compile/tests, run litmus, fix findings, restage, rerun until PASS, then commit.
   - Do not proceed to commit/push/PR while any staged group still has medium/high litmus findings.
