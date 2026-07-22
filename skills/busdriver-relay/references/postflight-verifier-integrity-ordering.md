# Postflight verifier integrity ordering

Use this when reviewing or implementing a gate that runs project verifier commands and then authorizes a draft result.

## Required ordering

Verifier commands are executable repository code and may mutate the worktree, index, HEAD, ignored files, `.git/hooks`, or authority markers even when they exit zero. Therefore:

1. Load and authenticate the preflight baseline.
2. Optionally perform an early integrity check for fast failure.
3. Run all configured verifiers in the sanitized runtime.
4. After every verifier has completed, freshly recompute:
   - repository root and HEAD;
   - tracked, staged, and untracked changed paths;
   - scope include/exclude violations;
   - hook inventory and hashes;
   - authority-marker inventory, types, and hashes;
   - ignored-file inventory and hashes;
   - any other invariant used by the returned decision.
5. Build `ok`, `changed_files`, evidence, and the final decision only from that post-verifier snapshot.

If checks occur only before verifiers, a passing verifier can violate every checked invariant afterward while the gate still reports success. Sanitizing the verifier environment does not solve this ordering bug.

## Review probe

Add a negative contract test whose verifier exits zero after writing an out-of-scope file or changing an authority marker. The postflight gate must return blocked and its final evidence must name the mutation. A second probe can move HEAD or alter a hook to ensure those inventories are also refreshed.
