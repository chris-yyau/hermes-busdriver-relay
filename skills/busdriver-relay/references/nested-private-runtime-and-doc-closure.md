# Nested private-runtime and documentation-closure hardening
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this note when a reviewed delivery path copies authenticated scripts or tools into temporary/private runtimes, or when policy documentation is guarded by link/semantic inventory tests.

## Transitive private executable closure

A private outer bundle is not sufficient if a nested script recopies a child into a second directory and loses sibling resources.

Required bundle shape:

```text
<bundle>/
  scripts/<parent>
  scripts/<child>
  trusted-bin/{git,gh,jq,...}
```

Rules:

1. Authenticate every script and executable before materialization.
2. Preserve the complete bundle topology across every nested invocation. Prefer executing the authenticated child in the existing mode-0700 bundle rather than copying only that child elsewhere.
3. Pass an explicit private-runtime marker into descendants. In private mode, missing/non-directory/symlink `trusted-bin`, or a missing/symlink executable entry, must fail closed.
4. Never fall back to the original installation path while the private marker is active. Hashing an original path and then executing it still leaves a replacement/TOCTOU window.
5. Confirm actual `argv[0]` paths for Git/GH/JQ and other children resolve inside the private bundle—not merely that hashes match.
6. Scope cleanup around bundle creation itself, child execution, assertion failures, timeouts, and normal exit.

### Regression probes

Cover all of these independently:

- complete bundle: child remains beside `trusted-bin` and every resolved executable is private;
- missing private directory: structured fail-closed result;
- symlink private directory or entry: structured fail-closed result;
- nested child copy mutant: demonstrate that moving only the child loses closure;
- hostile ambient `PATH`/original executable paths: prove they are never selected in private mode.

A unit test that monkeypatches `PRIVATE_TRUSTED_BIN` is not enough. Add an end-to-end probe that reproduces the real outer bundle → parent → child topology.

## Authenticated hash dependency order

After changing a production child:

1. hash the child;
2. update the parent’s embedded child pin;
3. hash the parent;
4. update the delivery executor’s embedded parent/child pins;
5. hash the delivery executor;
6. update the trusted-runtime manifest;
7. run manifest-binding contracts.

Any later edit to a pinned file restarts the chain. Do not reuse an earlier digest or candidate tree.

## Immutable review generations

- Create a new immutable boundary after any byte edit.
- A lane whose end verifier detects source drift is `INVALIDATED`, not `CLEAN` or a source verdict.
- Findings from a stale lane remain repair inputs when they reproduce on current bytes, but its verdict never transfers.
- All final lanes must review the same digest and independently rebuild the same candidate tree.
- Use `GIT_OPTIONAL_LOCKS=0` for read-only Git inspection so reviewers do not perturb immutable-worktree metadata.

## Documentation inventory closure

1. Treat every classified non-historical active document as a traversal root, not only a hand-curated root list.
2. Scan links in every such document and require each repo-local Markdown target to be classified.
3. Do not let an existing repo-local document escape through an `external_or_unavailable` bucket.
4. Test standards-valid CommonMark forms: inline, reference, HTML, escaped labels, multiline reference labels, destination-on-next-line, nested labels, balanced/escaped parentheses, angle destinations, and fragments.
5. A regex scanner must have explicit mutants for each form; prefer a CommonMark AST parser when the dependency is acceptable.

## Semantic policy clauses

Do not exempt an entire sentence merely because a blocker token appears somewhere in it. Evaluate adversative clauses separately:

- `blocked, but production launches …`
- `although blocked, production launches …`
- `while blocked, production launches …`
- `production launches … despite policy_blocked`

Avoid naïvely splitting every comma: that can separate legitimate negation from the capability phrase and create false positives in clean documents. Split only recognized adversative constructions, then rerun the guard over every active policy document—not just the mutants.

## Smoke runtime budget

A smoke wrapper can become invalid even when the suite is green if its timeout is below measured runtime. Set a contract-enforced budget with material headroom, run the embedded suite, and distinguish:

- embedded test timeout/failure;
- expected dirty-worktree gate rejection;
- clean rebuilt-candidate smoke success.

Always rerun the complete smoke on the clean rebuilt frozen candidate before accepting the generation.
