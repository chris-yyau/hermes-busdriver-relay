# OpenCode standalone adapter proof audit

Use this reference when auditing or promoting an OpenCode fallback/comparison adapter while Pi remains the only production implementation launcher.

## Separate four independent states

Do not collapse these into one boolean:

1. **Configured route** — live config selects `opencode` for secondary/fallback roles.
2. **Adapter contract verified** — schema, validator, negative contracts, and a real-model smoke pass.
3. **Programmatic production dispatch allowed** — the production launcher can select the adapter.
4. **Mutation/finalization authority** — commit, push, PR, merge, marker, deploy, release, publish, and finalization permissions.

A safe standalone-only promotion can be:

```text
selected_agent = opencode
adapter_verified = true
programmatic_dispatch_allowed = false
dispatch_blocker = opencode_standalone_adapter_only
mutation_allowed = false
finalization_allowed = false
```

Pi can remain the only production implementation lane while OpenCode is a verified standalone proof/comparison adapter.

## Read-only audit sequence

1. Capture the exact target worktree, branch, HEAD, and dirty state. Treat sibling worktrees and installed skill copies as evidence, not as the target implementation.
2. Inspect production parser choices, not only dead `agent_command()` branches. A complete-looking OpenCode branch is unreachable if argparse only permits `pi|noop`.
3. Inspect the standalone wrapper from input through acceptance: guard check, child environment, canonical prompt, result-size/type checks, schema validation, actual Git state reconciliation, scope include/exclude, HEAD preservation, redaction, and exit status.
4. Search for helpers that exist but have no call sites. Dead hardening helpers plus RED tests mean the proof is incomplete.
5. Run the narrow tests individually, then the whole relevant contract file. Report exact pass/fail counts; do not treat an internally consistent stale status suite as proof of adapter readiness.
6. Query live config and live resolver output separately. Configured routes do not imply dispatchability.
7. Compare repo skill source with the installed skill. Do not wholesale copy an installed tree that is ahead and contains policy wording inconsistent with current production CLI behavior.
8. Update status, docs, ADRs, repo skill source, and installed skill only after the executable proof is green and a current real smoke passes.

## Standalone wrapper acceptance checks

A strict validator alone is insufficient. The wrapper must independently reconcile model claims with repository reality:

- capture baseline HEAD and repository state before launch;
- require HEAD unchanged after launch;
- enumerate actual tracked, staged, and untracked changes;
- reject include-scope misses and exclude-scope hits;
- require artifact `files_changed` to exactly match actual changes;
- reject missing, malformed, oversized, symlinked, or non-regular result artifacts;
- reject nonzero process exits paired with a successful artifact;
- preserve all root and nested authority flags as exact false-only key sets;
- strip ambient secrets and risky Git environment from the child;
- use a canonical JSON template in the prompt, explicitly forbidding guessed aliases such as `authority_flags`, `git`, `scope`, and `notes`.

If the wrapper runs under a PATH guard, its own repository inspection must use a separately resolved trusted Git executable. Calling bare `git` after placing a blocking shim first in PATH makes newly wired reconciliation helpers fail themselves.

## Minimum negative contract set

Cover at least:

- out-of-scope write;
- scope-exclude violation;
- changed HEAD or absolute-path Git bypass attempt;
- artifact/actual changed-file mismatch;
- missing and malformed result;
- oversized and symlinked result;
- timeout and missing executable;
- nonzero process with success-shaped artifact;
- unexpected root authority-like field;
- extra nested authority field;
- blocked result with `ok=true` or no blockers;
- production launcher rejects OpenCode when policy is standalone-only.

Remove contradictory tests rather than weakening policy: do not retain both “production rejects OpenCode” and “production routes OpenCode” as simultaneous contracts.

## Real-smoke evidence rule

A historical real smoke from a sibling worktree can prove that a model followed a canonical artifact prompt and that an outer gate reconciled its changes. It does not prove that the current target wrapper's standalone reconciliation is wired. After the target code and negative contracts are green, run one current opt-in throwaway-repo smoke and retain the prompt, result, command metadata, and postflight evidence.

## Documentation synchronization

Use one precise phrase across status, README, CURRENT_STATUS, authority maps, ADRs, and skill copies:

> verified standalone draft adapter / fallback-comparison proof lane; not production-dispatchable; Pi remains the only production implementation adapter; all finalization authority remains false.

Avoid both stale extremes: “adapter not verified” after proof passes, and “programmatic dispatch allowed” when production parser policy still rejects OpenCode.
