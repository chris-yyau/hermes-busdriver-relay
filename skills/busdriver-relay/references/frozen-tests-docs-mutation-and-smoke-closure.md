# Frozen tests/docs mutation and smoke closure

Use this reference for independent frozen-review lanes that must verify documentation policy inventories, executable help truth, hermetic tests, exact-version smoke, and mutation resistance without editing the candidate.

## Documentation inventory mutants

Exercise the real inventory helper, not a hand-written approximation. Redirect its manifest/path globals to temporary files outside the candidate and require rejection of:

- canonical and normalized links: `references/x.md`, `./references/x.md`, `../...`, fragments, angle-bracket destinations, and reference-style Markdown links;
- legal CommonMark reference definitions with escaped closing brackets in labels, for example `[x\\]]: references/new.md` paired with `[policy][x\\]]`;
- legal reference definitions whose destination begins on the following line after the colon;
- duplicate entries within one classification;
- the same path appearing in two classifications;
- unknown roots, missing files, unreachable classified files, and newly linked unclassified files.

For syntax-shaped findings, prove the sample is a real link with an independent CommonMark parser and then show the production inventory helper accepts or misses it. Do not report a regex concern without both parts of that reproduction. Include legal multiline reference labels (for example a use of `[foo bar]` paired with a definition label split as `[foo\nbar]: ...`), not only escaped labels and next-line destinations; CommonMark normalizes the line ending to whitespace, while regexes that exclude `\n` from labels silently miss the link.

Seed traversal with every classified current document (`current_agent_policy` and `current_reference`), not only a small primary-root set. A classified active doc can be absent from the discovered graph when other docs mention it only in code spans/backticks; append a simple CommonMark link to such a non-root current document and require the real inventory target to reject the newly linked unclassified target.

Validate classification arrays as unique and pairwise disjoint **before** converting them to a dictionary. A dict comprehension silently collapses duplicates and can turn an active document into historical treatment.

Semantic activation guards must reason per clause, not exempt a whole sentence because one earlier clause contains `blocked`, `unavailable`, or `policy_blocked`. Add every-active-doc mutants using contrastive forms such as `Although production dispatch is blocked, production launches agents`, `While ... blocked, ... runs agents`, and `launches ... despite being policy_blocked`; require the complete real docs target to reject each.

Treat `external_or_unavailable` as another fail-closed classification boundary:

- require its entries to be unique and disjoint from current/historical classes;
- an existing canonical repo-internal Markdown target may not be excluded as external;
- add a mutant that removes a linked current document from its class and adds the same path to the external list; the real helper must reject it rather than silently dropping it from traversal and semantic sweeps.

When loading a test module with `runpy`, mutate the helper function's `function.__globals__`, not only the returned namespace.

### CommonMark reference-definition reproduction discipline

Do not accidentally make a parser mutant vacuous. A reference use followed immediately by its definition can remain part of the same paragraph and fail to parse as a reference link. Put a blank line between the use and definition, then independently require a CommonMark parser to emit the expected `href` before evaluating the production inventory helper. Known-valid shapes include:

```markdown
[policy][x\]]

[x\]]: ../../docs/new-policy.md#current

[next policy][next]

[next]:
  ../../docs/new-next-policy.md#current
```

For each syntax mutant, preserve three separate facts in evidence: the independent parser emitted an `href`; the production helper missed or accepted the target; and the real docs pytest target stayed green in a derived candidate. A helper-only acceptance is weaker than a surviving real target.

For internal-to-external reclassification, mutate a derived inventory by removing one non-historical document from its internal class, adding its SKILL-relative path to `external_or_unavailable`, and appending a contradictory production-capability sentence to that document. Run the complete real docs module. A green run is blocking; also record any reduction in parametrized test count, because disappearing semantic cases prove the inventory mutation changed the tested surface rather than killing the mutant.

## Rendered help is an active policy surface

A blocker constant somewhere in executable source does not prove truthful `--help`. For every production agent/verifier entrypoint:

1. run `--help` in a fresh isolated environment;
2. require the exact fixed blocker or an equally explicit statement that production returns nonzero before dispatch;
3. run semantic activation mutants against the rendered help;
4. retain source/docstring checks separately.

Flags for workers, models, timeouts, or repository preservation can otherwise make an unconditionally blocked parser look dispatchable.

## Large fixture cleanup is part of test correctness

`tmp_path` does not guarantee immediate deletion: pytest intentionally retains recent basetemp generations. A test that copies a package tree, model, repository, or toolchain under `tmp_path` can therefore pass while leaving hundreds of megabytes and tens of thousands of directory entries per run.

For every large shadow-copy test:

1. run it once with an explicit fresh `--basetemp`;
2. after pytest exits successfully, inspect whether the shadow root still exists and record its allocated size plus file/symlink counts;
3. test same-device hardlink and cross-device copy fallback behavior—cross-device `copy2` turns a cheap-looking fixture into real disk growth;
4. wrap the large subtree itself in `TemporaryDirectory` or `try/finally: shutil.rmtree(...)`, so cleanup happens even when an assertion fails;
5. add an after-test cleanup assertion outside the fixture scope.

Do not dismiss retained test artifacts because production state is unaffected. Repeated full/smoke lanes can exhaust CI disks or inodes and are a state-integrity blocker at the appropriate severity. Clean only reviewer-created paths after recording evidence; do not delete unrelated pytest retention roots.

## Exact-version smoke without candidate mutation

Run smoke from a verifier-reconstructed candidate that still has its `.git` metadata. Do not use a plain `git archive` of the candidate for Git-sensitive tests: the missing repository metadata can produce false failures in status/brief/readiness tests.

If the installed external plugin changes during review:

1. record the live version/commit drift separately;
2. locate the exact previously observed commit in the plugin repository;
3. verify `package.json` at that commit contains the requested version;
4. archive that commit to an external temporary plugin root;
5. run smoke from the verifier-reconstructed candidate against the archived plugin root;
6. record smoke internal rc, plugin version, exact pytest total, and sentinel non-leakage.

Do not imply the archived plugin is still the live marketplace checkout. This establishes requested-version compatibility while preserving truthful live-state reporting.

## Efficient closure order

Once a blocking mutant is reproduced, save it to the formal report immediately. Complete only the required evidence matrix, then reserve the final calls for: repeated descendant tests, end verifier, identity comparison, final report replacement, and report checksum. Avoid duplicate full-smoke reruns from invalid archive-only candidates; they consume closure budget without adding valid evidence.
