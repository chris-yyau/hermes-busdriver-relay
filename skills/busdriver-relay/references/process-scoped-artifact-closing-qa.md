# Closing QA probes for process-scoped artifacts and state-envelope consistency
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference for frozen correctness lanes that review a process-scoped HMAC artifact/status design and must finish with a strict START/END ceremony.

## Closing order under a hard call budget

1. Make the verifier `START` the first substantive action; skill loading is preparatory, but do not inspect the candidate first.
2. Reserve calls for: findings draft, `END`, reading only draft/START/END, formal report, sidecar generation/verification.
3. Complete every candidate read, focused test, and reviewer-owned probe before the findings draft.
4. Write the findings draft before the closing-call threshold, with exact identity, raw evidence, root-cause counts, and a provisional verdict.
5. Run `END` after the draft. After `END`, do not reopen candidate/source bytes; derive the report only from the draft plus START/END records.
6. Generate `report.md.sha256` from the finalized report and verify it with an independent checksum command. Require payload and process exit status to agree for START, END, and sidecar checks.

## Do not let a green suite replace semantic probes

A passing full suite and focused regression set are evidence, not a CLEAN override. Add reviewer-owned probes for behavior that existing tests assert only partially.

### Fixed blockers

Use hard sentinels for credential-capable status/discovery, run-ID creation, lock acquisition, artifact writes, and worker/network dispatch. Invoke the production `main()` path. Verify fixed blocker reason, null/echo-only run identity, null creation timestamp, no artifact path, and truthful `skipped` lock telemetry.

### Process-scoped status authentication

Exercise both controls from the same probe harness:

- **same process:** writer signs an artifact, live key remains in memory, status lookup returns `found=true`;
- **fresh process:** the key is not inherited, lookup returns `found=false` with the documented authentication-unavailable reason.

A fresh-process negative control alone does not prove the legitimate same-process path works.

## Artifact lookup needs semantic as well as cryptographic validity

A valid MAC authenticates the writer and bytes, not the meaning of the payload. Before accepting an artifact, correlate at least:

- top-level `ok` with decision/run outcome;
- `decision.status` with `run.status`;
- `decision.reason` with `run.reason` when the contract says they represent the same delivery result;
- mode/operation with run phase;
- reusable authority flags with all nested authority summaries.

Probe this by asking the real writer to sign a structurally valid but contradictory payload. The lookup must reject it. This catches producer regressions that unsigned-forgery tests cannot.

Do not treat one `verified` control as sufficient proof of top-level `ok` correlation. Build an operation-specific outcome matrix and include at least:

- a successful non-verify mutation (for example `commit`/`committed`) with only `ok` flipped to false; it must be rejected;
- a known failure with only `ok` flipped to true; it must be rejected;
- decision/run changed together to an arbitrary but internally equal unknown status/reason; it must be rejected;
- mutating-run operation/status/reason drift independently from decision/run; each must be rejected.

A partial predicate such as “false rejects `verified`, true rejects `blocked`/`*_failed`” is not a complete correlation contract: it can admit successful mutation envelopes with `ok=false` and invented statuses. Prefer an explicit operation → phase → allowed `(ok, status, reason)` mapping, including documented delivery-status and post-side-effect/release-failure exceptions.

### Bind the mutating transcript, authority, and writer—not only the top-level tuple

The exact contract must also define `mutating_run` cardinality for every operation/phase:

- verify, PR-grind, and pre-mutation `delivery_status` outcomes must forbid a mutating transcript;
- actual mutating phases must require one for success, blockers, reconciliation, release-failure, and post-side-effect outcomes;
- a validator shaped as `mutating_run is None or (...)` is incomplete unless the operation/phase matrix separately proves when `None` is legal.

Correlate nested mutating authority with the accepted outcome. Internal shape checks are insufficient: reject a blocked result carrying `allowed=true` and positive operation authority, a normal success carrying denied authority, and any authority reason that drifts from the mutating-run reason. Preserve the documented authority truth for reconciliation, release failure, and completed-side-effect artifact-write failure rather than deriving it from top-level `ok` alone.

For post-side-effect artifact-write failures, validate the mutating run against a separate set of allowed **original** mutation outcomes. Do not search the outer allowed-outcome set by matching status alone: that set also contains the artifact-write-failure tuple and can recursively admit `artifact_write_failed_after_side_effect` as both the outer failure and the supposed original mutating reason.

Run positive controls first, then exercise negatives at two layers:

1. call the production validator directly for precise diagnosis;
2. have the real production writer sign the contradictory payload, then require same-process direct lookup and production status lookup to reject it.

Unsigned forgery tests or direct-predicate tests alone do not prove that authenticated status lookup enforces the semantic contract. Keep each signed probe in a reviewer-owned artifact directory outside the candidate and clean it before the final inventory.

## Distinguish unavailable keys from malformed authentication

A helper that reports “process-external artifact exists but its key is unavailable” must first validate the complete auth-envelope shape, including schema, algorithm, key ID, MAC presence/type, and reasonable encoding/length. An unknown key ID with a missing MAC is malformed, not authenticated-but-unavailable.

Treat misclassification as a diagnostic-integrity finding even when it remains fail-closed and cannot authorize mutation.

## Completed-side-effect error reconciliation

When a side effect succeeds but durable artifact writing fails, preserve two truths without contradiction:

- the mutating-run transcript may retain the completed operation status/reason and record a separate artifact-write error;
- the top-level decision and delivery-run envelope must agree on the final delivery-level artifact failure reason.

Tests should assert top-level decision, delivery run, mutating run, steps, exit status, artifact path, and authority fields together. Checking only decision-vs-mutating status can miss a stale delivery `run.reason`.

## Filesystem-safe artifact storage and authenticated freshness

A process-scoped MAC does not make path traversal, lookup, or winner selection safe by itself. Review the storage boundary as a separate security protocol.

### Refuse every symlink component and keep I/O descriptor-relative

For a configurable artifact root, rejecting only the final directory symlink is insufficient: an intermediate component can redirect both writer and lookup. On POSIX, walk from `/` one component at a time with an already-open parent directory fd and `O_DIRECTORY|O_NOFOLLOW`; create missing components only with descriptor-relative `mkdir`, then re-open no-follow. Keep the final directory fd alive across temp creation, fsync, atomic replace, post-write identity confirmation, and rollback.

The writer should use same-directory descriptor-relative `O_CREAT|O_EXCL`, `replace`, and `unlink`. Lookup should use `listdir(fd)`, `openat`/`dir_fd` with `O_NOFOLLOW`, then `fstat`; never fall back to path glob/read after proving the directory. After replace, re-open the configured path and compare directory `(dev, ino)` with the original fd. Both a re-open failure and an inode mismatch must unlink the final artifact through the original fd before returning a write-failure envelope. Add deterministic tests for both branches and count open fds before/after.

### Bound and de-block hostile entries

Open candidate entries with `O_NONBLOCK` as well as `O_NOFOLLOW`, so a FIFO cannot block before `fstat`. Before reading, require a regular file, current UID, one link, owner-only mode, and an explicit maximum size. Then independently read at most `limit + 1` bytes to catch post-`fstat` growth. The producer must enforce the same byte limit on the final signed serialization **before** creating a temp file; otherwise it can emit bytes its own reader later rejects.

Treat parser failures as entry-local rejection. Besides decoding and `JSONDecodeError`, bounded hostile JSON may raise `ValueError` (for example integer digit limits) or `RecursionError`; neither should escape into an unstructured traceback. Probe real FIFO/non-regular entries, oversized files rejected before parser invocation, growth after `fstat`, exact-limit producer/reader parity, short-read loops, temp cleanup, and fd closure.

### Bind location and path claims, not only basename

A MAC that adds only `path.name` permits a byte-for-byte signed artifact to be copied into another safe artifact root under the same filename while the process key remains live. Bind the full absolute **lexical** discovered path into the MAC, and separately require all payload path claims (top-level artifact path and nested artifact references) to equal that discovered path exactly. Positive controls must prove lookup at the original path works; relocation, filename changes, body path changes, duplicate/missing references, and same-process re-signing of contradictory path claims must reject.

### Never use mutable filesystem metadata as freshness authority

`mtime`, `ctime`, directory order, and filename sort are mutable and unauthenticated. They may be used for diagnostics, never to choose the authoritative artifact. If one process can write multiple artifacts for the same run ID, put a positive process-local monotonic sequence in the MAC-covered payload and require it in the validator. Select the maximum sequence only after full schema and MAC validation; use a deterministic filename tie-break solely as impossible-duplicate defense. Consume sequence values on failed writes rather than reusing them.

Make final filenames independently unique (for example a random UUID component). Timestamp-second + run ID + PID can collide and atomic replace will silently overwrite the earlier signed artifact. Tests should freeze time/PID, write twice, prove both files survive, then mutate both mtimes in the wrong order and prove the larger signed sequence still wins. Also reject missing, zero, negative, boolean, and string sequences even when a same-process test re-signs the body.

### Keep process scope and documentation truthful

Test same-process lookup and fresh-process lookup separately. A fresh process has no in-memory writer key and must report the documented authentication-unavailable result; persisted bytes are not cross-process readable until an external broker exists. Documentation must not present a later CLI invocation as successful retrieval. Distinguish this from `run_not_found` and from malformed authentication wherever the status schema supports that signal.

## Finding accounting

Keep probe failures separate from root causes. A useful default classification is:

- missing authenticated state correlations or contradictory delivery envelopes: normally Medium unless they create reusable authority or unsafe dispatch;
- malformed-auth diagnostic spoofing that stays non-authorizing and fail-closed: normally Low.

Always justify severity from reachability and consequence, not from the number of failed assertions.
