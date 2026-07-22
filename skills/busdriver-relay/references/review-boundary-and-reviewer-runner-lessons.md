# Review boundary and reviewer-runner lessons

Use this when freezing Busdriver candidates for immutable multi-review, especially after a BLOCKED iteration with accepted reviewer findings.

## Boundary construction must match the verifier, not intuition

- Before a boundary becomes the review authority, run the same START/candidate closure verifier that reviewers will rely on. If it rejects the boundary, treat that file as a superseded candidate; do **not** edit sealed artifacts. Create a new boundary file that records the supersession reason and SHA-256 of the rejected candidate.
- `candidate_tree` must be rebuilt from the boundary's authenticated entry inventory, not taken from `git write-tree` on the repo index. Rebuild in an isolated temporary index/object directory by `git hash-object -w --stdin` for each recorded file, `git update-index -z --index-info`, then `git write-tree`.
- `source_digest_sha256` must use the verifier's canonical entry-list JSON bytes: `json.dumps(entries, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()`. Do not substitute a raw line/record digest.
- Dirty counts must match the verifier's live inventory. Use `git status --porcelain=v1 -z --untracked-files=all` for dirty/untracked counts, and `git diff --cached --name-only -z` for index path counts. A boundary made with a different untracked mode may fail START closure even when file bytes match.
- Keep `source_entry_count`, `dirty_record_count`, `tracked_changed_count`, `untracked_count`, and `index_path_count` in the boundary and in the verifier's hard-coded expected fields. Patch the review verifier/candidate closure constants together with boundary/digest/tree constants before running START.
- Prefer generating verifier constants from the authenticated boundary in one deterministic step. If adapting a prior iteration's verifier, search it for every stale generation, candidate-tree, digest, boundary-path, and count literal before the first START. Updating only the boundary path/digest while leaving a prior `generation` or `EXPECTED_TREE` must fail closed.
- Before applying `uchg`, run a boundary-only/scratch-lane preflight using the exact production verifier routines. Seal only the first verifier-compatible boundary. If a sealed candidate is rejected, preserve it as superseded rather than rewriting it, and make the final disposition identify the single boundary that actually entered the review chain.

## Stage immutable flags around closure writes

`uchg` is part of the evidence model, but applying it too broadly too early can prevent the verifier itself from completing. **Immutability is a filesystem flag, not a permission-mode rewrite.** Boundary entry digests include each file's mode, so `chmod -R a-w` after reconstruction changes the candidate even when every byte and executable bit is unchanged.

1. Seal the authenticated boundary and sidecar before reviews.
2. After START reconstruction, preserve every reconstructed mode exactly and apply only `chflags -R uchg` to each **review-view**. Immediately run candidate START closure with `require_immutable=true`; require exact path, mode, byte digest, entry count, and no missing immutable flags. Keep the lane directory and reviews root writable while prompts, reports, run metadata, END closures, and disposition are still being created.
3. Run source END closure while the lane can still `chmod`, create private verifier state, and perform exclusive/atomic output writes. Then run candidate END closure against the still-immutable review-view.
4. Write and checksum the final `CLEAN.md` or `BLOCKED.md`. Only then recursively seal the lane trees, reviews root, and review kit.

If pre- or post-review candidate closure reports a digest mismatch, the lane is invalid even when `paths_match=true`. Do not restore modes or otherwise "repair" the reviewed view after the model ran; create a fresh lane from the sealed boundary, apply only immutable flags, prove candidate closure before review, and rerun the reviewer. Preserve the rejected lane as process evidence and exclude it explicitly from final authority.

Recovery rules:

- Verifier closure writers are exclusive. If a retry reports `output_exists`, do not delete or overwrite the artifact automatically. Read it and accept it only if `ok=true`, the expected phase is present, boundary/source identities match, and candidate closure still reports `require_immutable=true` with no missing flags.
- An immutable parent directory can make `chmod`, temporary-file creation, or atomic rename fail even when the intended target is new. Diagnose flags on the lane/root and target first. If a write is genuinely still required, clear `uchg` only on the minimum parent directory—not recursively on authenticated review-view files—perform and verify the write, then reseal.
- If the disposition or closure already exists and is immutable, verify its sidecar/content instead of attempting to replace it. Existing valid immutable evidence is authoritative; repeated writes only risk breaking the chain.

## Validate reviewer runs before accepting verdicts

- A reviewer process exiting `0` is not enough. Empty reports, missing `VERDICT:`, CLI usage errors, denied tool prompts, or auth/login output are invalid runs. Preserve their stdout/stderr/result metadata, mark them invalid by run number, and rerun with corrected plumbing; never count an invalid run as CLEAN or BLOCKED.
- Keep each rerun's report/result paths distinct (`run1`, `run2`, ...). The final disposition must cite the valid run for each lane.
- For Codex CLI reviews, stdin plumbing is stable: `codex exec --sandbox read-only --cd <immutable-view> -` with the prompt on stdin.
- For Claude CLI reviews, be careful with variadic tool flags such as `--allowedTools`/`--allowed-tools`; if a prompt is positional, the flag can consume it. Prefer stdin with `--print --input-format text`, or otherwise verify the prompt reached the model. `--bare` skips OAuth/keychain/first-party login and expects explicit API-key-style auth; use non-bare mode when the configured first-party CLI auth is the intended credential source.
- For Antigravity/Gemini (`agy`) print mode, put flags before `--print <prompt>`. Before an expensive review, run a tiny read-only workspace probe that names two or three known top-level files. If the sandbox cannot see a candidate outside its default workspace, add the immutable view explicitly with `--add-dir <review-view>` or provide a compact inline evidence bundle. Permission bypass is acceptable only when combined with a sandbox, an already-immutable review view, disabled mutation/network scope where supported, and post-review candidate closure. Validate that the final report is non-empty and contains a verdict; exit `0` plus an empty/permission-denied report is invalid.

## Inline bundles should be compact and targeted

- Do not dump the entire repo into a reviewer prompt by default. Build a compact inline bundle around the sensitive production functions, their trusted-runtime pins, and focused RED/GREEN regressions.
- Include exact evidence values: boundary SHA-256, source digest, rebuilt candidate tree, full-test partition counts, fixed-point output, local/full required-check status, preflight blocker, and production secret-scan result.

## Sequence before declaring CLEAN

1. Reproduce each accepted finding as RED in the mutable next iteration.
2. Apply minimal production/test updates.
3. Refresh trusted-runtime pins until the official fixed-point script reports no changed scripts and no manifest change.
4. Run focused, affected, broad/full tests and hygiene/gates.
5. Build a verifier-compatible boundary, seal it, and verify sidecar checksum.
6. Run START and candidate START closures for every review lane; make the review views immutable before candidate START.
7. Run fresh reviewers; reject invalid/empty/no-verdict runs and rerun with corrected CLI plumbing.
8. Only after valid Codex, Claude, and Gemini reports all say CLEAN on the same immutable candidate may the iteration be considered CLEAN.
