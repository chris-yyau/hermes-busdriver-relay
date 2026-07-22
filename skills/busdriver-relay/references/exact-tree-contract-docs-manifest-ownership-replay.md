# Exact-tree contract, docs, manifest, and ownership replay review

Use this for final read-only reviews whose authority is a Git **tree object**, while the live worktree may be dirty or changing concurrently.

## Review boundary and footprint

1. Locate the Git dir, real index, and every required object directory with path-only discovery first; do not resolve the target object yet. Before any object-aware Git command, retain row-level opening manifests for every source, candidate, replay, and evidence object directory: relative path, file type, size, `mtime_ns`, and a separate semantic/content fingerprint. An aggregate hash alone proves drift but cannot localize it.
2. When the contract forbids **object-store metadata mutation**, make private byte copies of all required object databases under the authorized scratch root. Do not use hardlinks, because inode metadata remains shared. Point `GIT_OBJECT_DIRECTORY` and `GIT_ALTERNATE_OBJECT_DIRECTORIES` only at those private copies for the rest of the review.
2a. Freeze every verdict-bearing **non-object evidence file** at the same opening boundary: proposal/inventory JSON, replay scripts, commit plans, status records, and any other inputs the review will parse. Retain their row-level opening manifest, copy them by value into the authorized scratch root, and read only those copies during the review. A concurrent reconciler may legitimately add plans or rewrite evidence while the immutable target tree stays unchanged; reading live evidence at different times creates a mixed-generation review that cannot be sealed.
2b. Before declaring the opening generation complete, perform a **path-only evidence-dependency closure**. Without resolving Git objects or consuming payload semantics, enumerate path-bearing fields such as `old_artifacts`, inventory/proposal locations, replay stores, draft-PR/status records, and declared alternates; add every referenced file/store to the same opening manifest and private copy set. Do not discover a referenced historical inventory only after proposal inspection and then silently mix it into the generation. A supplemental seal is acceptable only when the referenced material has not yet been read and the report explicitly identifies the supplement; the preferred result is one complete opening seal.
2c. At opening, compare every caller-required live source path against the target map as well as recording the whole-worktree manifest. Repeat the same path CAS at close. This distinguishes “already stale at opening” from “changed during review”; a close-only CAS proves current mismatch but cannot by itself time the drift.
2d. Seal the **authority closure**, not a producer directory by name. Enumerate verdict-bearing files and every referenced dependency first, then manifest only that closed set. A growing progress/full-run log may be explicitly excluded only when no proposal, digest, plan, smoke verdict, or caller requirement depends on it; record the non-authority reason. If it is referenced, wait for a terminal generation and include it. Recursively sealing unrelated volatile logs creates an artificial opening-race blocker without strengthening the verdict.
3. Route all object-aware commands—including target resolution, status/tree reads, `cat-file`, `archive`, `diff`, `read-tree`, and `write-tree`—through the private copies with `GIT_OPTIONAL_LOCKS=0`. Some Git/object-store combinations can freshness-touch loose objects or pack metadata even during commands used as read-only evidence.
4. Record the named object type and resolve it as a tree; do not assume it is a commit.
5. Record live `HEAD`, `HEAD^{tree}`, real-index SHA-256, exact NUL-delimited porcelain-status SHA-256/byte count, ref/config fingerprints, and cache-artifact count. Preserve row data for every footprint whose differences must later be named.
6. Inspect target files with `git show <tree>:<path>`, `git ls-tree`, and `git cat-file`; never checkout/reset the source worktree.
7. Repeat the complete footprint at the end. Equal HEAD/index plus a changed status fingerprint means concurrent worktree drift, not permission to revert it. Name newly drifted paths separately while keeping the immutable-tree verdict independent.
8. Compare both original object-store metadata manifests and semantic/content manifests. Metadata-only object drift does not change the immutable target-tree verdict, but it blocks a strict no-mutation footprint PASS. Keep attribution uncertain unless a controlled probe proves whether reviewer access or a concurrent actor caused it.

## Independently rehash the target tree

Do not accept `git rev-parse <tree>^{tree}` as the independent proof. From recursive `git ls-tree -rz` leaf entries:

- re-read every blob and recompute `sha1("blob <len>\\0<bytes>")`;
- rebuild directory trees in memory using raw entry bytes `mode SP name NUL raw-oid`;
- sort directory entries with Git ordering (`name + '/'` for directories, `name + NUL` otherwise);
- recursively recompute `sha1("tree <len>\\0<payload>")` and require the root to equal the requested tree.

This writes no index or objects and catches bad snapshot/tree assumptions.

### Object-dependency closure and scratch reconstruction

Preflight whether supplied replay/commit-plan object stores are traversable under their **declared** alternates. A commit object can exist while its referenced final tree or latest blobs are absent because the builder relied on an external candidate-object directory. Keep two conclusions separate: the plan payload may be correct, while the retained object bundle is not self-contained.

When the target tree object is absent but an exact source snapshot was sealed at review opening:

1. Independently hash every snapshot file/symlink and rebuild all directory payloads in memory; require the root OID to equal the named target.
2. If Git traversal is needed for commit-chain or scanner checks, write only those already-verified blob/tree payloads as zlib-compressed loose objects under the authorized scratch root. Recompute each OID before writing.
3. Use the scratch target objects as the primary store and only private byte copies of replay/source stores as alternates. Never fall back to an original or undeclared ambient object directory.
4. Verify commit/tree correctness and retained-bundle self-containment as separate report rows; scratch reconstruction proves the immutable bytes, not that the supplied bundle was complete.

Implementation pitfalls:

- The replay base may be a commit while the review authority is a tree. Resolve `<base>^{tree}` before comparing an in-memory rehash; never compare a recomputed tree OID directly to a commit OID.
- Represent leaves with an explicit tagged type or tuple. Do not identify directories with `isinstance(value, dict)` when leaf metadata is also a dict (`mode/type/oid`), or the rehasher will recurse into leaf fields.
- Keep the target-tree blob rehash separate from proposal replay. A proposal reaching the named OID is not independent proof that every target blob and directory payload rehashes correctly.
- Treat serialized Git command arrays as command records, not blindly reusable argv tails. An inventory may retain the subcommand itself (for example `diff`) and a symbolic `HEAD`; strip the recorded subcommand before invocation, resolve the frozen linked-worktree `HEAD` through its `ref:` indirection in the copied common Git directory, require the resolved OID to equal the sealed expected commit, and record both literal and effective arguments.
- Reconstruct each inventory producer's **exact byte contract** before declaring payload drift. Historical transition `patch_sha256` values may bind `git diff --full-index --binary --unified=1` (including full 40-hex `index` lines), while a later-hunk inventory may use abbreviated index lines. Likewise, a historical per-hunk seal may hash the complete `@@ ... @@\n` header plus body even when a latest-hunk `payload_sha256` hashes the body alone. Never reuse one inventory's canonicalization for another merely because both describe Git hunks.
- If nearly every row fails the same hash comparison while old/new entries, numstat, and tree replay agree, classify the result first as a likely verifier-representation mismatch. Diagnose one sampled row against the producer/test contract and a bounded set of plausible flags/framing rules before emitting candidate findings; a uniform all-row failure is not credible evidence of hundreds of independent defects.
- For exact-once proofs, never use `Counter(mapping)` as a set oracle: mapping values become counts. Compare `Counter(observed_ids)` with `Counter(expected_mapping.keys())`, then separately require every count to be one.
- Reconcile independently generated structural-diff paths with evidence path notation explicitly. A verifier may emit slash paths such as `/source/foo` while the evidence uses JSONPath such as `$.source.foo`; normalize only the notation and still require the exact declared difference set.

## Stronger ownership replay than the proposal builder

Validate source inventories independently before trusting proposal counters:

1. Regenerate the canonical latest patch using the proposal's exact diff arguments and derive each hunk ID from canonical bytes. Require exact ordered record equality, unique IDs, path totals, and patch SHA-256.
2. Replay all historical transition units from the immutable base in canonical stage/inventory order. Before each update, require current `(mode,type,oid)` to equal the unit's declared `old`; require the old-only result to equal the recorded pre-remediation HEAD tree.
3. Replay the proposed slices again from flat path state, without the proposal's temporary index/object implementation.
4. Before installing each latest full-path target entry, require the current entry to equal that path's recorded HEAD entry. `git apply` succeeding is not a substitute for this temporal precondition.
5. Recompute each intermediate tree OID in memory. Derive changed paths and immediate numstat from consecutive flat maps; compare tree, paths, stats, owner counts, and caps with each proposal slice.
6. Require old-unit and latest-hunk source sets to match proposal owner-map keys exactly and every unit to be observed once.
7. Normalize independent reruns only at explicitly declared relocated runtime-path fields; enumerate every raw difference before accepting normalized equality.
8. If a commit plan exists only in an isolated replay object store, verify the entire parent/tree chain read-only through **private copies** of that replay store and its source alternates. Keep offline chain validity separate from rollout preconditions: compare every `old_head_expected` to current local/live refs as a temporal CAS check. A pre-existing ref mismatch does not alter the immutable tree verdict, but the plan must not be applied blindly until refs are freshly reconciled.

### Atomic-plan internal consistency and rollout CAS

Do not accept a top-level summary such as `all_bases_match: true` as proof that force-with-lease expectations are fresh. Check every plan row independently:

- require restack and atomic-plan identity for ordinal, slice, parent, tree, new commit, stats, caps, head/base refs, and `old_head_expected`;
- compare `old_head_expected` to any captured `live_old_head` in the same evidence;
- compare it again to the current local ref, and to a freshly read live ref only when live rollout state is in scope;
- enumerate mismatches row-by-row even if a top-level boolean remains true.

A mismatch is a concrete stale/broken rollout-plan finding—the plan must not be applied as-is—while the independently replayed immutable tree and offline commit chain may still pass. Keep those conclusions separate rather than converting one into the other. Perform the row-level local/live CAS comparison immediately after freezing and parsing the plan, before expensive focused tests. Latch any mismatch and reserve the remaining work for immutable-tree adjudication, close evidence, and reporting instead of discovering an already-blocking stale lease only after a long test run.

For the **executable** push plan, do not overload historical `old_head_expected` with live CAS authority. After all tree-bound tests and reviews pass, query every live PR/ref again and emit one unambiguous `lease_head` per row alongside `target_commit`, `head_ref`, and `base_ref`; keep historical expectations in a separate audit artifact. Reconfirm remote `main`, OPEN/Draft state, exact base/head names, head-repository ownership, required `(context, app_id)` protection, and runner inventory in the same fresh generation. Push the whole stack with `git push --atomic` plus an explicit `--force-with-lease=refs/heads/<ref>:<lease_head>` for every ref, then re-read every PR head and require exact target commit equality. A non-atomic multi-ref force push or a plan with mixed stale/live lease fields is not sealed delivery evidence.

## Runtime-manifest fixed point

Against target-tree blobs, independently require:

- `production_entrypoints` equals the Git mode-`100755` script surface in both directions;
- every repo-local digest in script, adapter-runtime, delivery-status-runtime, and production-entrypoint sections equals target bytes;
- every quoted 64-hex literal in tracked scripts is represented by an authoritative manifest value;
- every exact-source provenance exemption in contract/scanner tests—full-file SHA-256, AST fingerprint, or fixed dispatch allowlist—matches the target bytes it is meant to authorize;
- focused manifest-contract tests pass on an exact target snapshot;
- whenever a production entrypoint changed, the exact-tree production dispatch-surface/scanner tests also pass. A manifest can be internally correct while a stale provenance sentinel makes the scanner fail closed; that is a sealing defect, not a harmless test-only mismatch.

Do not infer completeness from manifest self-report alone; Git modes and tracked files are the independent surface.

Manifest namespaces are not automatically repository paths. Before hashing, derive each section's path semantics from the schema, production consumer, and contract tests: one section may use repository-relative paths, another may use basenames under a fixed `scripts/` root, and a plugin section may identify blobs at a separately pinned upstream commit. Do not prepend paths or classify a section as repo-local merely because similarly named files exist in the target tree; prove the namespace, then hash the correct authority.

## Scanner-safe fixture rewrites

When credential-shaped test literals are split or concatenated to stop repository secret scanners from flagging inert fixtures, source similarity is not enough. Preserve test semantics explicitly:

1. Parse the pre-change and target test blobs as ASTs.
2. Constant-fold scanner-sensitive outer string expressions where safe, keyed by file/function, and compare value length plus SHA-256 rather than printing credential-shaped text.
3. For expressions containing repeated padding or local variables, compare the foldable literal prefix/suffix and confirm the unchanged dynamic operands; bound any multiplication before materializing it.
4. Run the affected redaction/scanner test nodes on the exact-tree snapshot.
5. Separately require the target source scanner to find no raw credential URI prefix.

Report pre-existing runtime fixture values separately from any new scanner-closure sentinel introduced only in the target tree.

### Whole-stack scanner-safe tips

A clean final target is insufficient when the deliverable is a stacked plan: scan the raw blob bytes of **every slice tip**, not only each slice's changed paths. Deduplicate reads by blob OID for efficiency, but retain `(ordinal, tree, path, oid)` attribution so a finding can be assigned to the first unsafe tip.

- Search both the repository's credential-shaped URI regex and any dangerous value produced by source-level literal concatenation (for example, compare raw bytes against `b"https://" + b"x-access-token:"`, not only the two harmless-looking source fragments).
- Independently verify temporal deferrals: every historical unit in the declared unsafe transition interval belongs to the scanner-closure slice, the final scanner-safe production bytes land in that same slice, and earlier tips do not expose the pattern.
- If an old transition first introduces a scanner-shaped literal before the final hygiene bytes are available, delay the **contiguous unsafe suffix** of that path's historical units to the closure slice, preserve their canonical order there, and apply the final safe bytes last in the same commit. Do not merely move the hygiene hunk earlier when later historical units would overwrite it, and do not replay the same remediation hunk multiple times. Recompute dependencies, immediate numstat, caps, one-owner coverage, and every intermediate tree after the rebalance.
- Require the scanner-closure slice's relevant production entry to equal the final target entry, then continue scanning later tips to prove it is not regressed.
- Reconcile the independently observed unique-blob count and zero-finding set with any supplied stack-local scanner evidence. A final-tree scan cannot substitute for this per-tip proof.

## Documentation graph closure

Run the repository's real link grammar (inline links, reference definitions, HTML `href`, and single-backtick local Markdown paths) against target-tree blobs. Traverse only declared roots plus independently derived ADR roots. Require:

- every discovered doc has exactly one classification;
- every active classified doc is reachable;
- declared external/unavailable targets do not exist or duplicate classified docs;
- every historical doc has its required superseded/non-production banner;
- README/status inventories cover the manifested production surface and clearly separate unsealed current bytes from historical evidence.

A virtual in-memory filesystem avoids consulting a concurrently changing worktree.

Do not replace the repository grammar with a generic `` `anything.md` `` regex over every Markdown blob. Command snippets, placeholders, home-relative paths, and historical cross-repository citations can look path-like without being authoritative local links. Start from the declared roots, apply the real source-specific normalization rules, and traverse only the classifications whose outgoing edges the contract defines as authoritative. Check historical documents' required banners independently; follow their outgoing links only when the shipped grammar explicitly does so. The real focused docs tests remain the adjudicator for grammar parity.

## Required-check source contract

Check the exact tree, not a live workflow copy:

- the lock's required context maps to the workflow job's effective check name;
- the required portable job uses a GitHub-hosted runner and explicit allowlist;
- no self-hosted/host-runtime job or lock context survives;
- pull-request triggering cannot skip the required context through path filters;
- isolation/cache flags are present and the allowlisted tests are traced for transitive host assumptions.

When deriving the portable allowlist, parse only the actual pytest command tail (for example, text after `python -B -I -m pytest`). Do not regex the whole job block: comments may mention host-specific tests that are not executed, creating a false host-assumption finding.

Parse workflow jobs with a real YAML parser when available, or with an indentation-aware line scanner that terminates only at the next **exact two-space job key** under `jobs:`. Never delimit a job with a substring split such as `text.split("\n  ", 1)`: that token also begins four-space nested fields like `name:`, `runs-on:`, and `steps:`, so every valid job can be truncated and falsely reported as missing its required name/runner. If all required jobs fail the same source-contract predicate, print one sampled extracted section and validate the extractor before blaming the workflow.

Keep this source-contract conclusion separate from live branch-protection or hosted-CI rollout state.

## Exact-tree focused tests without touching the source repo

When executable verification is needed, create a temporary snapshot under the authorized external runtime root, not in the source repo or system `/tmp`:

1. make private byte copies (not hardlinks) of the candidate, source, and any replay object databases under the external review root before the first target-object Git command;
2. run `git archive <tree>` only through those private object copies and extract into the snapshot;
3. before `git init`, explicitly unset inherited `GIT_OBJECT_DIRECTORY` and `GIT_ALTERNATE_OBJECT_DIRECTORIES`; initialize Git only inside the snapshot;
4. after initialization, use the snapshot's own `.git/objects` as the primary `GIT_OBJECT_DIRECTORY` and expose only private copied databases through `GIT_ALTERNATE_OBJECT_DIRECTORIES`; never point the scratch repository's primary object directory at an original or evidence store;
5. `git read-tree <tree>` into the snapshot index and require `git write-tree` to equal the target;
6. Before executing pytest, run the exact selectors with `--collect-only -q` under the same interpreter/environment and count collected cases. Treat file-level selection as unbounded until measured: parametrization can turn a handful of “focused” files into more than a thousand tests. If the caller gave a numeric test cap, refuse or narrow selectors until the collected count is at or below the cap; never infer compliance from the number of files or node selectors.
7. Run `python -B -I -m pytest -p no:cacheprovider --basetemp <external-dir> ...`. If logging output, preserve the pytest exit status explicitly (`set -o pipefail` plus `${PIPESTATUS[0]}` in Bash), or redirect stdout/stderr to a file and capture `$?` before reading it. A green summary line is not a substitute for a recorded zero exit code, and a `tee` pipeline can otherwise make the wrapper status ambiguous.
8. scan for `__pycache__`, `.pytest_cache`, `*.pyc`, and `*.pyo`;
9. delete all copied object databases, snapshot, and basetemp paths and verify no leftovers.

An unborn scratch repository reports every indexed file as staged relative to no commit. Compare scratch status before/after rather than requiring zero; `write-tree == target` is the byte identity proof.

### Worktree/common-dir and inherited-environment pitfalls

- Derive a linked worktree's common Git directory from the frozen `.git` gitfile plus `commondir` semantics; do not infer it from a nearby clone or rescue-directory name. Copy that exact common object store by value. When checking retained-bundle self-containment, use only the replay primary and the exact declared common/candidate alternates; an ambient extra alternate can hide an incomplete bundle.
- Scope `GIT_DIR`, `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, and `GIT_INDEX_FILE` to object-aware setup commands. Before pytest—especially tests that initialize nested repositories—run with those variables explicitly unset so Git uses cwd discovery inside the snapshot and each nested test repo. Otherwise tests can silently inspect the source repository or write nested objects into the wrong scratch store, producing plausible but false manifest/scanner failures.
- Set `TMPDIR`, `TMP`, and `TEMP` to an existing directory under the authorized review root for executable tests. Tests that create commits may invoke globally configured SSH signing, which needs a valid temporary directory; an inherited stale temp path can look like an object-database failure.

### Scanner pattern fidelity

Replay the repository's exact credential scanner patterns first. If adding a generic HTTPS-userinfo check, require credential-bearing userinfo such as `https://user:secret@host` (a colon before `@`). Do not classify the intentionally redacted diagnostic form `https://***@host` as a credential finding. Keep the raw concatenated sentinel check (`b"https://" + b"x-access-token:"`) separate so source-level literal splitting cannot bypass it.

## Close-footprint and tool-budget discipline

Treat close evidence and scratch deletion as acceptance gates, not optional epilogue:

- reserve enough tool-call budget for one batched close operation before opening long files or adding optional test breadth;
- create and syntax-check the deterministic close/cleanup script at review opening, while all path manifests and scratch locations are known. Once core verdict-bearing checks and mandatory focused tests pass, run that single close operation before optional broad test expansion; do not spend the reserved close call debugging optional breadth;
- make broad verifier output bounded and failure-class aware: cap/de-duplicate repeated row errors, stop a family after a small sample, and preserve a compact ledger outside terminal scrollback. A monolithic verifier that emits hundreds of identical hash/parser failures can consume the remaining tool budget and prevent the mandatory close; diagnose the first systemic mismatch before continuing the family;
- split long reviews into idempotent, independently sealed phases (inventory/history, ownership replay, commit chain, per-tip smoke, manifest/docs, close) and persist one canonical result digest per completed phase. Before a bulk phase, exercise one representative row and its set/count assertion. A late harness defect must resume at the failed phase rather than rerun hundreds of already-proved transitions and exhaust the close budget;
- front-load reusable scripts, but batch final HEAD/tree/index/status/ref/config/cache fingerprints, row-level metadata/content comparisons, drift localization, artifact scan, and scratch deletion into a deterministic close phase;
- invoke the close/cleanup command from a stable parent directory outside the scratch root. Deleting the process's current working directory can produce a post-success `getcwd`/`pwd` error and make an otherwise valid close status ambiguous. Compute the canonical closing-seal hash before deletion, delete the exact owned scratch root, verify absence, and emit both the seal hash and cleanup result;
- run the close phase before extra explanatory inspection once all verdict-bearing checks are complete;
- never claim a strict no-mutation footprint PASS until the opening and closing manifests have been compared and authorized scratch leftovers are gone;
- if live evidence drifts after the opening snapshot, do not silently re-read or rebase individual files mid-review. Finish only against the frozen generation, report the evidence drift as a seal blocker, and require a fresh whole-review generation if the updated evidence itself needs approval;
- when the caller requires that a live source path **still equals** the named target, perform a fresh close rehash of that source and compare every latest-owned path entry against the opening target map. A one-path drift can leave the frozen proposal/commit-plan review fully valid while still blocking the requested live-source PASS; report both truths and do not attribute the drift without controlled evidence;
- if an external tool ceiling interrupts before close, mark the review incomplete and name the missing close proof rather than treating successful semantic checks as a final PASS.

## Report shape

Lead with `PASS` or bounded findings. Report target identity, source-inventory counts, exact ownership coverage, slice maxima versus caps, manifest/docs/required-check closure, focused test counts, and a separate footprint/drift note. State all durable files created or modified; transient snapshots deleted successfully count as no retained files.

When the user explicitly requests **“PASS or concrete findings only”**, that instruction overrides the fuller ledger above: return exactly `PASS` if clean; otherwise return only the concrete finding(s), each with evidence/location, reproduction, and impact. Do not append a passing-check inventory, accomplishment summary, or general narrative unless an incomplete close/cleanup is itself a finding.
