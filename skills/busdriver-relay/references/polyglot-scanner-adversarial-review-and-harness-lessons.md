# Polyglot scanner adversarial review and harness lessons

## Trigger

Use this reference when a frozen Busdriver candidate changes static dispatch/scanner policy, when one reviewer reports scanner bypasses that other reviewers miss, or when a large settled-source suite must be partitioned without weakening evidence.

## One blocker overrides another lane's CLEAN

Independent reviewers are complementary, not a vote. A `CLEAN` from one lane never cancels a concrete reachable High/Medium finding from another lane. The boundary is blocked as soon as one finding is validated.

For a blocked boundary:

1. preserve each raw reviewer output and exit metadata;
2. generate candidate/view end closures and run verifier `END` before source mutation;
3. validate each finding with an executable RED regression where feasible;
4. repair source only after the round is closed;
5. rebuild a new content-addressed boundary and require every final lane to review that same new snapshot.

A reviewer process exit, provider `exit 0`, progress narration, or a report link is not a formal verdict. Require a durable report ending in exact `VERDICT: CLEAN` or `VERDICT: BLOCKED — ...`; keep raw output and report hashes as provenance.

## Reviewer-launch failures do not invalidate unchanged source

If a reviewer never inspected source because of CLI/auth/tool-permission setup, archive the failed attempt and retry only after the failure. Reuse the same immutable boundary only when source/candidate/view are unchanged.

Preflight each lane without reading candidate source:

- CLI syntax and model availability;
- auth status in the intended private HOME;
- headless read-tool permission behavior;
- report/output path writability outside the immutable view;
- worktree/non-worktree requirements;
- timeout large enough to reach a final verdict.

Use a minimal private HOME with only the required auth material and settings. Keep model transport credentials outside prompts and reports. Combine plan/read-only mode, sandbox restrictions, an OS-immutable review-view, and prompt-level scope restrictions; no one layer substitutes for the others.

Archive each failed attempt under `attempts/attempt-N/` instead of overwriting it. A retry report must not silently inherit a stale report from the failed attempt.

## Explicit environment for every subprocess

Do not rely on the terminal session's inherited `HOME`, XDG paths, or Git configuration: earlier isolated commands may persist exported values, while a real user HOME may inject signing, hooks, config, caches, or credentials.

Every reviewer/test partition must explicitly set:

- isolated `HOME` and XDG config/cache/data roots;
- isolated `TMPDIR` and Python bytecode/cache roots;
- the exact auth/config directory needed by the selected provider;
- explicit Git global/system config policy;
- a fixed working directory.

For test partitions that create temporary Git commits, isolate or disable global/system Git config so user-level signing policy cannot turn source-correct tests into environment failures. Preserve the failed raw logs, fix the harness, and rerun in new clean partition roots; do not reinterpret an environment avalanche as a source regression.

## Full-suite partition evidence

Never reuse an old partition list after tests or parametrization change. Re-run `pytest --collect-only`, parse exact node IDs, assert the expected total, then partition the new list.

Each partition should produce:

- exact node list and count;
- raw stdout/stderr log;
- payload exit code;
- start/end timestamps;
- SHA-256 sidecar for node list and log;
- isolated HOME/TMP/XDG/Git state.

Aggregate only after verifying every sidecar and payload exit. The sum of passed and skipped nodes must equal the fresh collection total. A shell wrapper's exit must agree with the pytest payload; if they disagree, rerun rather than declaring GREEN.

## TDD for scanner findings

For every proposed bypass:

1. construct syntax-valid source in the target language;
2. prove the current scanner accepts or misses it (`RED`);
3. reject examples already producing `unparsed_*`, syntax failure, or another fail-closed violation—they are not bypasses;
4. make the smallest scanner change;
5. run the new regression plus nearby positive/negative controls;
6. run the complete scanner contract and then the full suite.

High-value composition classes:

### JavaScript lexical context

Do not decide regex-vs-division from the preceding character or keyword alone. Track the previous significant token and control-parenthesis state. Contextual identifiers such as `of` can be identifiers, properties, `for-of` separators, or operands inside classic/`for-in` expressions. Include compositions such as `for (let x in of / payload / 2)` and genuine `for (x of /regex/)` controls.

### Python data-flow and mutation

Source-order bindings must cover:

- subscript writes and deletes;
- starred/unpacking assignments;
- mutating methods and dunder mutators;
- aliases that refer to the same argv object;
- builtins/import loader aliases;
- unresolved process-callable receivers and dynamic member selection.

When an alias mutates a security-relevant argv object, invalidate every conservatively related spelling. Unresolvable process/dynamic-code members should fail closed for security-relevant API names; add local-object controls where false positives are plausible.

### Shell quote/substitution seams

A quote is escaped only when preceded by an odd run of backslashes. Validate even/odd parity, nested legacy/modern substitutions, comments, and EOF. To prove a real quote bypass, use a Bash-valid fixture where the scanner finishes without `unparsed_shell:*` yet misses an executable command; a malformed fixture that already fails closed is not evidence.

### Exact provenance identity

Never key a security exemption only by `path.name`, suffix, or `endswith(...)`. Bind AST/source fingerprints to canonical repo-relative paths. Test a same-basename copy under a different directory and ensure it receives no exemption. Apply the same canonical-path rule to launcher fingerprints, env sanitizers, broker exemptions, shell wrapper hashes, and any authenticated-source carve-out.

## Patch safety in very large dirty files

For large WIP files, use unique surrounding context for targeted patches. Fuzzy replacement can consume an adjacent constant or declaration while still producing syntactically valid output. After every patch:

1. inspect the returned diff;
2. run syntax/type diagnostics immediately;
3. restore any accidentally changed neighboring declaration before further edits;
4. do not execute tests against a known malformed intermediate state.

Preserve a hash-bound baseline outside the repo before delegating a large-file repair. Whole-file draft writers are unsuitable for multi-hunk edits near size limits unless their complete replacement semantics are deliberately used and verified.

## Acceptance gate

Scanner repair is not complete until all are true:

- every validated finding has a RED→GREEN regression;
- nearby false-positive controls pass;
- scanner contract file passes;
- fresh full-suite collection and isolated partitions pass;
- fixed-point pins and manifest checks pass;
- index/ignored/pycache hygiene is clean;
- latest `origin/main` ancestry is revalidated;
- a new immutable boundary is reviewed by all required lanes with formal CLEAN reports and START/END closure.
