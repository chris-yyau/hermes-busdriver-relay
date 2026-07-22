# Immutable review finding follow-up lessons

Use this note when a Busdriver iteration has already passed focused/affected/full tests and an immutable review is being closed.

## Core rule

Passing gates is not a delivery decision. If any valid immutable reviewer reports High/Medium `VERDICT: BLOCKED`, stop delivery, preserve the sealed artifacts, adjudicate each finding, and open the next mutable repair iteration for accepted findings. Do **not** PR-grind, merge, or rewrite the sealed boundary/review kit to make the report fit.

## Findings that green tests can still miss

- **Retained fd to a mutable regular file is not immutable bytes.** If credential-bearing helper bytes are digest-checked and then Bash reads `/dev/fd/<fd>`, a same-UID attacker may still truncate/write the same inode after hashing and before shell read. For accepted findings in this class, add a focused RED that mutates the same inode after authentication, then fix by transferring verified bytes through an immutable channel (for example an anonymous pipe/read-end with exact authenticated bytes, or another mechanism that cannot observe later file mutation), not by passing a regular-file fd that stays live to the original inode.
- **Separate helper bounds from executable bounds.** Guard code for private helpers must enforce `MAX_AUTHENTICATED_HELPER_BYTES` (or equivalent helper-specific cap), reject oversized `fstat` metadata before reading, and read at most bound+1 before hashing. Do not let helper validation inherit a much larger executable-size cap.
- **Cleanup scope starts immediately after `Popen`.** For process-group-owned children, initialize drain/thread variables defensively and enter the `try`/cleanup scope before constructing or starting drain threads. A `Thread.start()` failure or `KeyboardInterrupt` in that setup window must still kill/reap the owned group.
- **Credential alias drift is a real bug.** When a tool declares `CREDENTIAL_ENV_KEYS`, derive child env allowlists and auth predicates from that tuple, or test every alias. A declared alias that is omitted from forwarding/auth checks can make token-only enterprise runs silently fall back to the wrong auth path.

## Reviewer-run validity checks

- An empty report, setup/login prompt, or permission-denied transcript is **not** a clean review. Record it as invalid and rerun with a valid read-only reviewer or a corrected invocation.
- For headless workspace-isolated reviewers, make the immutable `review-view` visible using the reviewer’s read-only workspace mechanism (for example an explicit `--add-dir <review-view>` style option) rather than weakening the immutable snapshot. Keep the snapshot read-only/`uchg`; permission bypass for reading is only acceptable when filesystem immutability prevents mutation.
- Require a clear final verdict. No-verdict reports must be rerun or excluded from the three-review closure.

## Closure/disposition pattern

1. Keep prior blocked iteration artifacts immutable and checksum-verified.
2. Copy accepted findings into the next mutable iteration as focused RED tests.
3. Repair minimally, refresh trusted-runtime pins to fixed point, and rerun affected/broad/full gates.
4. Build a new immutable boundary/review kit only after the mutable tree is green.
5. Run fresh reviews against that sealed snapshot; only a CLEAN review set permits delivery.
