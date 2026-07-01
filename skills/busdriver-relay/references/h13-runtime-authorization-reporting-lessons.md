# H13 Runtime Authorization Reporting Lessons

Context: Hermes Delivery Mode run for `hermes-busdriver-relay` PR #16 (`feat: report runtime authorization sources`). The slice hardened `scripts/hermes-busdriver-runtime-check` without adding any finalization authority.

## Durable lessons

### 1. Runtime-check should report authorization sources, not grant authority

`hermes-busdriver-runtime-check` is read-only evidence. It may observe facts such as hook-shaped stdin or the presence of `hermes-busdriver-gate`, but it must not convert those observations into mutation/finalization authority.

A useful envelope shape is:

```json
{
  "runtime_equivalence": {
    "mutating_launcher_allowed": false,
    "authorization_sources": {
      "claude_hook_runtime": {
        "observed": false,
        "authorized_here": false,
        "reason": "hook-shaped stdin is observed only; runtime-check does not grant mutation"
      },
      "explicit_equivalent_gate_runner": {
        "available": true,
        "path": ".../scripts/hermes-busdriver-gate",
        "authorized_here": false,
        "reason": "use hermes-busdriver-gate/agent-draft, not raw runtime-check"
      },
      "local_non_finalizing_draft": {
        "authorized_here": false,
        "reason": "allowed only through draft gate pattern, not read-only runtime-check"
      }
    }
  }
}
```

### 2. Hook-shaped stdin is only an observation

A normal Hermes process can feed JSON that resembles Claude Code hook stdin. That proves only that the checker can parse hook-shaped input; it does **not** prove that subsequent shell commands will be intercepted by Claude Code `PreToolUse`/`PostToolUse` hooks.

Keep both fields explicit in tests:

- `inside_claude_code_hook_invocation` / `claude_hook_runtime.observed` may be true.
- `mutating_launcher_allowed` and every `authorized_here` field must remain false.

### 3. Gate runner availability is not runtime-check authorization

`hermes-busdriver-gate` being present/executable is useful status evidence, but the correct action is to route implementation through the gate/agent-draft pattern. Do not let runtime-check become an alternate launcher or authority oracle.

### 4. Contract tests should cover normal shell and hook-shaped stdin

For this class of reporting, tests should assert both:

- normal shell: `observed=false`, `authorized_here=false`;
- hook-shaped stdin: `observed=true`, `authorized_here=false`.

Also assert that equivalent-gate availability is reported while remaining non-authoritative.

### 5. Draft verifier caveat: PATH guard and temp git commits

`hermes-busdriver-agent-draft` may run verifiers under a PATH guard. Full contract suites that create temp git repos and run `git commit` can be blocked by that guard even when the relay code is correct. Prefer scoped verifier(s) inside agent-draft, then run the full suite outside the draft guard as operator verification. Do not treat the PATH guard block as proof that the code failed.

### 6. Delivery pattern used successfully

For this small status-only slice, the successful finalization sequence was:

1. Codex implementation through relay draft/gate path.
2. Operator verification: targeted runtime test, full contract suite, py_compile, runtime-check envelope, deliver verify envelope.
3. Commit-mode litmus PASS, then synthetic `post-commit-consume-marker.sh` because Hermes finalization runs outside Claude runtime.
4. PR-mode litmus: Codex lead PASS, backstop PASS, `--write-pr-marker`, then synthetic `post-pr-consume-marker.sh` after successful `gh pr create`.
5. Latest-head PR-grind loop waited for checks/reviewer bots until clean.
6. Squash merge, branch cleanup, main sync, post-merge main CI watch, final clean `main...origin/main`.
