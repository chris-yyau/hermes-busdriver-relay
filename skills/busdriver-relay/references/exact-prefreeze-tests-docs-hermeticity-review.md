# Exact pre-freeze tests/docs/hermeticity review closure
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this for independent review of a named frozen candidate where `CLEAN` requires zero Critical, High, and Medium findings.

## Closure contract

A valid review has five gates:

1. **Start closure** — verify the boundary JSON's SHA sidecar, every recorded filesystem entry, expected source digest field, Git HEAD/tree/branch/remote/status shape, staged-path count, and source containment. Keep all source Git commands read-only (`GIT_OPTIONAL_LOCKS=0`, isolated global/system config).
2. **Independent rebuild** — create the reviewer candidate only inside the authorized lane. Reconstruct from the recorded HEAD, remove the checkout's worktree payload without touching `.git`, then copy exactly the boundary entries. Compute the candidate tree with a temporary `GIT_INDEX_FILE`; do not use the producer's candidate as proof.
3. **Targeted review/probes** — review tests, docs, rendered help, and hermeticity. Mutants and generated evidence must stay inside the lane.
4. **Fresh isolated suite** — use a fresh HOME/TMPDIR/XDG set, an interpreter known to contain pytest, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and `--basetemp` outside the candidate. Record the test process's own exit code in its log.
5. **End closure** — after every test and probe has stopped, repeat the complete boundary and read-only Git checks entry-by-entry. Generate the report and SHA sidecar only after this gate. If the full-suite result or end boundary was not collected, the review is `INCOMPLETE`, never `CLEAN`.

Treat a per-entry verifier as stronger evidence than merely trusting a producer-declared aggregate digest. Still record and compare the declared digest and sidecar; unexplained digest canonicalization is a limitation, not permission to invent a matching formula.

## Independent docs mutation matrix

Do not test only regex examples already present in the suite. Use an independent CommonMark parser and require it to emit the intended href before interpreting a negative mutant result.

Cover at least:

- inline and reference links;
- escaped destinations and escaped reference labels;
- multiline reference labels and newline reference destinations;
- nested labels and balanced-parenthesis destinations;
- angle destinations, entities, fragments, and repo-root logical paths;
- raw HTML links such as `<a href="references/new-policy.md">...`.

For each legal local-doc link form, create an unclassified target inside a derived candidate and run the real docs target. Distribute the forms across every non-historical classified document (or run the full cross-product when affordable), while separately exercising every document through the helper matrix. A green target means the inventory missed a semantically active link. Raw HTML needs both CommonMark rendering and HTML `href` extraction; a Markdown token-only scanner is insufficient. Cover double-quoted, single-quoted, and valid unquoted `href` attributes, entities, fragments, and case/attribute-order variations. Keep code-fence behavior consistent with the inventory's existing Markdown treatment so examples do not become an unreviewed alternate path.

## Semantic blocker mutation matrix

A sentence-level blocker check is unsafe if any blocker word suppresses the entire sentence. Exercise clause position and conjunction order against every non-historical classified document:

- leading subordinate clause: `Although/While/Even though production dispatch is blocked, production launches ...`;
- postpositive clause: `Production launches ... although/while/though production dispatch is blocked`;
- `despite`, `but`, `however`, `yet`, `and`, and `even though` variants;
- a bare comma boundary: `Production launches ..., production dispatch is blocked`;
- a positive claim plus an unrelated blocker token in the same sentence.

Require both the helper and the actual docs test target to reject every mutant. Append the mutant to each classified current document, not just one representative file. A helper unit test is not enough when surrounding document text changes tokenization. In addition to the helper matrix, create a derived candidate for every punctuation/conjunction family and run the real docs target: a green target is a finding even if narrower helper tests reject adjacent variants.

Run legal blocker controls too (for example, `Production never launches agents` and `Production launches no agent processes while dispatch is blocked`) so clause splitting cannot turn truthful negative guidance into a false positive.

Avoid solving suffix adversatives by splitting every `while`/`although` occurrence unconditionally. Legitimate blocker text such as `production dispatch ... while <blocker> is active` may rely on the suffix for its negation, and removing it creates false positives. A robust two-stage approach is:

1. handle leading `Although/While/Even though <blocker>, <activation>` by separating the comma-delimited clauses;
2. for suffix adversatives, split only when the preceding clause contains an explicit activation verb (`launches`, `dispatches`, `runs`, `executes`, `performs`, `enabled`, `verified`, `works`, `proves`), not merely the noun `dispatch`;
3. evaluate each resulting clause with the production-activation and negation patterns;
4. run the clean corpus before accepting the mutant fix.

Keep a positive control for legitimate blocker inventory bullets and rendered-help phrases. If adding truthful help causes the semantic sweep to flag `Production ... before dispatch`, include the blocker in that same help clause rather than weakening the detector globally.

## Rendered-help truth

For every production agent or finalization entrypoint:

1. Capture real `--help` output.
2. Invoke each fixed-blocked operation with harmless nonexistent/lane-local arguments.
3. Compare the actual nonzero reason with the help text.

Help must contain the exact fixed blocker or an equally explicit statement that production returns nonzero before dispatch. Parser flags, "gated" wording, lock claims, or descriptions of a dormant execution sequence must not imply that a fixed-blocked operation runs. Add tests for all production wrappers and the delivery dispatcher, not only one smoke command.

## Hermeticity probes

For package-shadow helpers, prove both paths:

- **same filesystem:** source and destination share `st_dev`, files are hardlinked during the context, and the shadow disappears afterward;
- **cross filesystem:** source and destination differ in `st_dev`, files are copied rather than hardlinked, and the shadow disappears afterward;
- **partial failure:** wrap `copy2` so it materializes one destination file and then raises; confirm the partially copied tree is removed.

Record file/symlink counts during the cross-filesystem copy so the probe cannot pass without exercising a real tree. After focused tests and the full suite, scan the candidate for `.pytest_cache`, `__pycache__`, and `.pyc` artifacts and inspect basetemp for leaked shadow directories.

Postflight residue checks must avoid two classification mistakes:

- Match actual shadow destination names/expected structure, not any pytest node directory whose test name merely contains the word `shadow`.
- Separate candidate/source contamination from artifacts confined to the external basetemp or a synthetic child HOME. Count confined bytecode/cache artifacts, prove they never entered the candidate/source, clean the reviewer basetemp before END, and report the observation; do not silently relabel confined test artifacts as source contamination.

Write a machine-readable candidate postflight record containing the entry digest, mismatch list, candidate cache/bytecode list, exact shadow residue list, and reviewer-basetemp cleanup result. Finish optional probes early enough to preserve calls for complete END verification, the formal report, its SHA-256 sidecar, and a sidecar verification.

## Identity-bound prior evidence

A later formal ceremony may use pre-existing probe evidence only as **supplemental identity-bound evidence**, never as a substitute for the new START/END closure or fresh critical controls. Before citing it:

1. independently verify every candidate entry record, canonical source digest, recorded HEAD, and candidate tree with a temporary index;
2. establish that the earlier evidence names or otherwise binds to that exact candidate identity;
3. rerun the focused baseline and the highest-risk controls inside the new ceremony;
4. label older matrices as identity-bound prior evidence in the report rather than implying they were generated after START.

This is especially useful when broad mutation matrices already exist but the producer omitted the formal closing ceremony. Findings remain valid when byte identity is proven; ceremony evidence does not.

## Semantic vocabulary and clause-boundary expansion

Do not stop at comma/`and`/`yet` or the first adversative set. Independently probe clause forms such as `whereas`, em dash, colon, and `because`, plus direct capability synonyms such as `starts`, `spawns`, `invokes`, and `activates`. Treat two omission classes as separate root causes when appropriate:

- statement/clause decomposition lets a blocker token suppress a positive capability claim;
- the activation vocabulary never recognizes the capability verb.

Run both helper-level probes and the actual docs target across every active classified document. Keep truthful negative controls so vocabulary expansion does not make clean policy text fail.

## Same-UID artifact-authenticity probe

File mode `0600`, removal of a key-path environment variable, and a child-specific HOME do not by themselves isolate a signing key from a lower-trust child running under the same UID. For HMAC- or MAC-authenticated delivery artifacts, add a harmless child probe that:

1. observes which parent paths remain derivable from inherited environment/state;
2. attempts to locate and read the signing key as the same UID;
3. signs attacker-selected identity/freshness fields; and
4. submits the forged artifact through the real status/lookup verifier.

If lookup accepts the forgery, report an artifact authenticity/integrity finding. The durable fix requires a trust boundary the child cannot cross (for example a different UID, protected broker, or parent-only IPC), not path hiding or mode bits alone.

## Ceremony-safe report production

Draft the narrative report before END. After all probes stop and reviewer basetemp is cleaned, run the complete live END closure, write a machine-readable START/END comparison, and then do not read the candidate again. Produce the final report and `<report>.sha256` only from the draft and evidence lane. Finish with both `sha256 -c`-style verification and a machine-readable delivery check covering START, candidate identity, the authorized test exit, postflight, END, start/end equality, verdict text, and sidecar equality.

## Verdict discipline

Count root-cause findings once, assign C/H/M from impact, and report passing controls separately. `CLEAN` is allowed only when:

- C=0, H=0, M=0;
- the independent full suite completed successfully;
- containment/cache/cleanup postflight passed; and
- the complete end boundary equals the complete start boundary.
