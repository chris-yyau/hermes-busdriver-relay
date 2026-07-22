# Frozen production trust-boundary review: transitive ownership and outer-launcher lessons

Use this reference after an independent frozen review finds that the declared blockers and manifest hashes are locally correct but the production call graph is still not closed.

## 1. Test blockers at the top-level production entrypoint

A blocker deep inside the final mutation/helper is too late if `main()` first calls delivery-status, repository discovery, HOME/config resolution, GitHub/auth helpers, state/lock setup, or artifact persistence.

For every policy-blocked operation:

1. Load the real production entrypoint without executing it.
2. Replace the first credential-capable or stateful helper called by top-level `main()` with a fail sentinel.
3. Invoke the exact production CLI shape.
4. Require the fixed blocker envelope before the sentinel.
5. Repeat for every blocked operation independently; do not infer push ordering from merge or PR-create ordering.

A regression that proves only that the final `git push` / `gh pr create` / `gh pr merge` command did not run is insufficient.

## 2. Outer smoke/probe launchers are production entrypoints too

Do not stop tracing at an inner launcher that blocks correctly. A production smoke or parser helper may still create a throwaway repository, inspect HOME, resolve PATH, or run a bare executable before invoking the inner blocker.

Probe outer launchers with a synthetic HOME, FIFO credential files, and fake same-name executables that write sentinels. Assert the fixed blocker, bounded completion, and absence of every sentinel. A throwaway repository does not make execution of ambient PATH bytes trusted.

If executable smoke behavior is needed only for tests, move it to a clearly non-installed harness. Keep the production smoke surface parser/authority-negative and side-effect-free before its blocker.

## 3. Runtime ownership is a transitive call-graph closure

Matching hashes for the declared entrypoints does not prove ownership closure. Starting from each side-effect-capable production owner, enumerate every directly executed helper and repeat transitively.

For each reachable helper, require:

- an authoritative manifest mapping;
- runtime digest authentication;
- execution of the authenticated bytes (private copy, fd-bound seam, or equivalent);
- tests that fail when a newly reachable helper is not mapped.

Pay special attention to read-only helpers such as delivery-status: they can still be credential-capable, inspect HOME/repositories, and run before a later mutation blocker. A helper used before a policy blocker belongs to the protected boundary even if it never mutates by itself.

## 4. A pinned executable does not make its invocation environment trusted

Digest/path validation answers “which executable bytes?” It does not answer “which host, repository, loader, config, or credentials will those bytes use?” Review the exact child environment at the dispatch boundary.

- Build from an allowlist; do not inherit the full parent environment and then remove a few known names.
- Forward only the credentials the operation requires. For GitHub CLI lanes, explicitly decide whether token-only auth is supported and preserve only approved token variables.
- Scrub host/repository selectors (`GH_HOST`, `GH_REPO`), loader/startup/toolchain redirects, Git config injection, shell startup variables, and ambient proxy variables unless policy explicitly owns them.
- Bound credential-bearing subprocess stdout/stderr at the pipe. Shell command substitution is still an unbounded capture even when the resulting string is later truncated or parsed.
- Add a real child-boundary probe that emits presence booleans for approved credentials and sentinels for forbidden environment classes; testing only the environment-builder dictionary is weaker.

Inventory readers also need semantic completeness, not just trusted dispatch. For GitHub required-check enforcement, normalize both legacy `required_status_checks.contexts[]` and app-bound `required_status_checks.checks[]` (including app identity where policy binds it). A clean result derived from only one representation is not a complete inventory verdict.

## 5. Executable lookup itself is a pre-blocker interaction

Argparse defaults are evaluated while constructing/parsing the parser. Do not call `shutil.which()`, resolve PATH, read HOME, or inspect executable bytes in a default expression when the production policy says the command blocks immediately after argument parsing.

Use literal defaults, return the blocker, and perform lookup only in the post-blocker implementation branch. Add resolver/`shutil.which` fail-sentinel tests so “worker did not launch” cannot hide early lookup.

## 6. Documentation inventory must include implicit active surfaces

A complete policy inventory includes more than hand-selected README/SKILL files:

- tracked project guides loaded on fresh clone (for example `.claude/CLAUDE.md` or `AGENTS.md`);
- every current reference linked by the active skill;
- accepted ADRs;
- executable docstrings and help text;
- adapter READMEs and status documents.

Derive the inventory mechanically where possible. Require every linked document to be classified as current, historical/superseded, or target-state. Unclassified new links fail closed. Historical documents need a strong banner and must not retain unqualified current-tense production procedures.

## 7. Evidence packaging

Keep probes outside the frozen candidate. Save structured JSON for blocker-ordering, fake-PATH/FIFO, and runtime-identity results. Hash the final report after its last byte is written and store the digest in a companion `.sha256` file to avoid self-referential report hashes. Run the end verifier before final report finalization; identity closure does not override reproduced blockers.
