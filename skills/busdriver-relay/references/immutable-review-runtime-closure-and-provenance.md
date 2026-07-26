# Immutable review rounds, runtime closure, and provenance hardening
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when a Busdriver relay delivery has a large dirty WIP, authenticated runtime pins, multiple formal reviewers, or repeated pre-freeze rounds.

## 1. Treat each review round as a byte-identity transaction

A review round is valid only for one exact source inventory. Any source-byte, mode, symlink-target, tracked/untracked inventory, or index change invalidates the round.

Required sequence:

1. Finish focused and full tests, syntax/JSON/diff checks, ignored-artifact cleanup, and secret scanning.
2. Build an exact boundary from tracked plus untracked source entries; record bytes/hash, mode, symlink target, counts, dirty records, source digest, and candidate tree.
3. Compile and run `review-verifier.py --help` before creating lanes. Never infer a verifier CLI from an earlier round.
4. Give every lane an **absolute** lane path. A relative lane can place verifier-private runtime files inside the source repo and invalidate the boundary.
5. Let the verifier reconstruct its candidate when that is its contract; do not pre-populate a candidate unless `--help` explicitly says to.
6. Complete START source/candidate closure before review.
7. For long-context review, clone the authenticated candidate into a separate view, mark every entry immutable where supported, and verify candidate/view identity plus flags.
8. Run formal reviews read-only. A report is usable only when it actually addresses the prompt, has acceptable stderr/result metadata, and has exact END closures.
9. END-close source and every candidate; separately END-close immutable view identity/flags when the verifier reports source only.
10. Freeze only when every required reviewer is valid and has no policy-blocking severity. GREEN tests never substitute for formal review.

If a reviewer returns a greeting, empty report, tiny error summary, or otherwise ignores the task, treat it as an invalid attempt and retry with a previously verified invocation form. Do not weaken the reviewer set or count an invalid output as CLEAN.

A background tracker’s missing/`None` exit metadata is not stronger than direct evidence. Judge completion from process liveness, result/report files, stderr, and START/END closure together.

### Exact committed-tree closure review

When the authority is an exact base commit, candidate commit, candidate tree, and evidence patch, review Git objects rather than trusting the checked-out worktree:

1. Record base, candidate, `candidate^{tree}`, parent(s), symbolic ref, porcelain-v2 branch/status, index SHA-256, and a deterministic refs snapshot/hash. Use `GIT_OPTIONAL_LOCKS=0`; isolate global/system Git config when required.
2. Read candidate bytes with `git show candidate:path`, inventory with `git ls-tree -r candidate`, and diff with `git diff --full-index --no-ext-diff --no-textconv base candidate`.
3. Reconcile exact changed paths/statuses, numstat totals, and modes. For a digest-only refresh, require every added/deleted line to contain the expected digest literal, replace every 64-hex SHA-256 token in each before/after blob with one placeholder, and require the normalized bytes to be identical. This is stronger than AST/JSON equality and also proves formatting, paths, flags, and adjacent policy bytes did not move; AST/JSON comparison remains a useful second opinion.
4. Verify the root producer independently: hash the real bytes and, when part of the contract, prove literal path, non-symlink state, owner/mode, and trusted ancestry. Search the base tree for the old producer digest and the candidate tree for the new digest; require identical `(path, line)` consumer sites, old absent from candidate, and new absent from base.
5. For every changed authenticated helper, compute the base/candidate blob SHA-256, compare all old/new consumer sites, reject every stale old occurrence, build producer-to-consumer edges among changed helpers, and reject cycles. This proves the embedded DAG reached a fixed point rather than merely refreshing a manifest root.
6. Validate every repo-local manifest entry against the candidate **commit blob**, not disk bytes or a hand-picked subset. For external evidence, independently compare names/numstat/patch bytes, recompute declared hashes and proof before/after blob hashes, compare a supplied index with `git ls-tree -r candidate`, and validate supplied loose-object IDs after decompression. Historical pre-commit status evidence must reconcile its status code, path inventory, and base blob OIDs; never present it as current state.

Run focused closure tests under an approved runtime root with isolated `HOME`, `TMPDIR`, cache roots, `PYTHONPYCACHEPREFIX`, `PYTHONDONTWRITEBYTECODE=1`, cache-disabled pytest, and Git optional locks disabled. If a full suite contains one already-adjudicated host-pin drift, reproduce that exact node, deselect only its exact node ID, and report passed/skipped/deselected counts; do not relabel the remainder as an unconditional full-suite pass. After a timeout, first prove no test process remains, then remove every isolated runtime leftover before closing the review.

Recompute the same HEAD/tree/parent/ref/index/refs/status seal after all required checks. Any mismatch invalidates that temporal review window. Source/tree/index drift requires a full restart. If only Git metadata moved while HEAD/tree/index and the clean worktree remained exact, disclose the drift, open a fresh seal, rerun every required object/content check and focused authority test inside the new window, and close that window exactly; earlier exact-commit tests are supplemental evidence, not the new seal. If a stable reseal cannot be completed, return `BLOCKER`.

Bind the final `PASS`/`BLOCKER` to exact base/commit/tree/patch IDs and report digest-only proof, producer consumers, stale-hash count, helper DAG/manifest closure, test counts and exact deselections, seal result, and all temporary artifacts created and cleaned. Keep command-backed operator evidence separate from conclusions that could not be executed.

### Reviewer identity and transport are part of closure

- Record lane role, transport/provider, actual model identity, and artifact identity separately. A lane name is not provenance.
- A **Claude/Claude Code** lane must use the native first-party Claude CLI/runtime. Never substitute an Agy-routed Claude-family model or relabel a proxy route as Claude.
- If the required native reviewer is unavailable, preserve the failed attempt and mark the round BLOCKED. Do not silently weaken or replace the reviewer set.
- Agy or another proxy is valid only for a lane the user explicitly assigned to that transport, such as an Agy Gemini lane when requested.

### Prove the finding, not merely a rejection

Before changing source for a reviewer finding, reproduce the exact claimed bypass with a focused RED test. Assert the intended violation category/reason, not merely that the violation list is non-empty: a conservative scanner can reject the sample for an unrelated reason and conceal the original gap. Add nearby controls, then run focused GREEN, the full contract, and the full suite. Any source change invalidates every verdict and closure from the old round.

## 2. Keep source and review evidence separate

- Put candidate lanes, isolated HOME/TMPDIR, raw reviewer output, verifier-private binaries, and freeze artifacts under the approved runtime root, never the repo.
- Review prompts and reports may live in the lane; they must not enter source inventory.
- After a failed START that accidentally writes into source, remove the artifact, rebuild the boundary/verifier, and recreate all lanes. Never hand-wave the old boundary back into validity.
- Do not edit source while any formal reviewer is running. Use one canonical mutator per worktree between rounds.

## 3. Refresh digest closure to a fixed point

Runtime authentication is a graph, not a flat manifest. A leaf change can alter a wrapper, which alters an orchestrator, which alters delivery, which alters manifest expectations.

Use this algorithm:

1. Compute current hashes for authenticated leaf scripts and wrapper bytes.
2. Replace their embedded consumer pins and matching manifest entries.
3. Recompute every parent whose bytes changed.
4. Replace parent pins and production-entrypoint entries.
5. Repeat until a complete pass finds zero drift.
6. Assert manifest digests against actual disk bytes for **every** declared runtime entry, not just key-set equality or a subset.
7. Run focused runtime-manifest tests, then the full suite.

Cap the loop and fail if it does not converge. Report rounds and modified files. Do not update only the root digest while leaving embedded leaf pins stale.

## 4. Provenance is authority

- Caller-selected executable paths are test doubles, not production authority.
- Environment stripping and an alternate `HOME` do **not** sandbox arbitrary same-UID code; it can query the passwd database or read other user-readable files.
- Therefore arbitrary caller helpers must not execute in live production. Require explicit fixture/test mode, fail closed before spawning otherwise, and keep fixture output authority-negative.
- Trusted live helpers must be absolute, authenticated, retained against verify/use races, and invoked with isolated, allowlisted environments. Digest-checking a mutable path and later executing the path is insufficient.
- Treat helper output provenance explicitly in machine-readable envelopes. Structurally valid fixture JSON is not live authority.

## 5. Capability and output egress

- Status, handoff, diagnostic, and review envelopes must never expose lock-release tokens or other private capabilities. Emit a recursively sanitized public lock view with owner/PID/operation diagnostics only.
- Bound hostile output **before** regex redaction. If raw output exceeds the safe scan budget, emit a fixed oversized-output literal rather than slicing a fragment whose credential prefix may have been cut away.
- Redact exact credential environment values, URL userinfo, common provider tokens, JSON token fields, and stderr/stdout on both success and failure paths.
- Publication/mutation errors must preserve truthful side-effect state even if cleanup or redaction itself raises.

## 6. Path and glob safety parity

Apply one scope contract across gate, Python wrappers, JavaScript/TypeScript adapters, include rules, and exclude rules:

- Reject control characters, C1 controls, and Unicode line/paragraph separators in paths and patterns.
- On POSIX, reject backslash pathnames instead of rewriting `\\` to `/`; rewriting changes the file identity.
- Make `*`/`**` newline-safe and enforce true full-string matching.
- JavaScript `$` can match before a final line terminator. Prefer a real end assertion such as a negative any-character lookahead, or explicit whole-string equality after matching.
- Test include-pass and exclude-bypass cases with LF, CR, VT, FF, C1, U+2028/U+2029, and backslash.

## 7. Stop conditions and handoff truth

When a tool-call cap or provider limit interrupts the run:

- Do not say the relay is complete.
- State the last valid formal verdict, exact current boundary/closure state, which tests are grounded, and the next unexecuted gate.
- Distinguish agent self-reported test results from operator-verified results.
- Never proceed to freeze, refs, push, PR, merge, or cleanup of ownership until the required formal review and delivery gates actually complete.
