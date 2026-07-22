# Pre-freeze mode/operation and executable-closure probes

Use this during correctness/state-integrity review of a dispatcher whose policy depends on both a mode and an operation, especially when some combinations are permanently blocked and another combination can mutate Git state.

## Enumerate the full mode × operation cross-product

Do not enumerate fixed blockers only from operation helper bodies or a top-level blocker map. Build the Cartesian product of every accepted `--mode` and `--operation`, including combinations that look nonsensical (for example, an execute mode paired with a plan-only operation).

For each combination, determine whether the final verdict is unconditional. If it is, require the blocker before:

1. generated run identity or timestamp;
2. delivery/status or PR discovery;
3. repository and credential-capable helpers;
4. lock/state initialization;
5. artifact persistence.

Probe each fixed combination twice:

- without caller identity, with run-ID generation replaced by a hard-fail sentinel;
- with caller identity, with status/repository/lock/artifact helpers replaced by hard-fail sentinels.

Also include the most credential-capable accepted flags, such as a PR number. An unconditional `unsupported_operation` returned only after delivery status is a blocker-ordering defect even if no artifact is ultimately written.

## Trace executable closure on every reachable mutating path

Manifest hash agreement is necessary but insufficient. Starting from every dispatchable mutation (commit as well as network operations), trace every subprocess edge through preflight, safety checks, helpers, cleanup, and reconciliation.

Flag both of these patterns:

- **bare executable edge**: `subprocess.run(["git", ...])`, even when PATH is fixed to root-owned system directories, if the authority manifest pins a different executable;
- **hash-then-execute TOCTOU**: hash an original absolute path and later pass that same mutable path to `Popen`/`run`.

A fixed PATH is environment hardening, not byte authentication. A root-owned system binary may still differ from the manifest pin or change across OS updates.

The safe pattern is:

1. identify and retain the **logical trusted tool name** (`git`, `gh`, or `jq`) before rewriting `argv[0]`;
2. open/read the pinned executable bytes;
3. verify the digest of those bytes;
4. materialize those exact bytes into a private mode-`0500` file under a mode-`0700` runtime directory;
5. retain the runtime guard until the subprocess has completed;
6. execute only the private copy;
7. require every direct and transitive `argv[0]` to resolve inside that private runtime.

Do not compare the rewritten private path to the original installed path to decide tool-specific environment behavior. After `argv[0]` becomes `/private/.../gh`, a check such as `effective_argv[0] == TRUSTED_GH` is false and may silently strip GitHub credentials. Route credentials and other tool-specific policy from the retained logical tool identity, while still executing only the private path.

If private copies are cached, key the cache by logical name, authenticated source identity, and expected digest. Revalidate `lstat`, non-symlink type, exact mode, and digest before reuse. A missing or modified cached copy must fail closed; it must not silently fall back to the original executable. Tests should cover cache/source changes, private-copy tampering, and lifetime through `Popen.communicate()`.

Regression tests must assert the complete `argv[0]` path, not merely `Path(argv[0]).name == "git"`. Include preflight helpers such as Git config and common-dir/hooks discovery; these are frequently missed because the final mutation command itself already uses a trusted wrapper. Include a credential-routing control proving private `gh` receives only the approved GitHub variables while private `git` does not.

## Pin refresh after closure changes

Executable-closure fixes commonly alter several authenticated scripts. Refresh pins in dependency order, never by ad hoc search-and-replace:

1. hash the innermost checker/helper;
2. update its parent loop pin and hash the loop;
3. update dispatcher/runtime inventories and hash the dispatcher;
4. update every manifest section that records those entrypoints;
5. refresh independently changed wrapper/help entrypoints;
6. run the manifest contract plus production materialization before the affected/full suite.

A stale embedded runtime hash can make dozens of unrelated delivery tests fail as `delivery_status_runtime_integrity_failed`; diagnose the first authenticated materialization boundary before treating the downstream failures as separate defects.

## Severity guidance

- A fixed blocker that reaches credential-capable discovery or synthesizes durable identity first is normally High correctness/state-integrity impact.
- An unpinned or TOCTOU executable reachable from a dispatchable mutation is at least Medium and may be High when it can influence destination, refs, index, hooks, credentials, or the mutation decision.
- Count all affected mode/operation combinations or subprocess sites by shared root cause, while preserving the raw affected list.
