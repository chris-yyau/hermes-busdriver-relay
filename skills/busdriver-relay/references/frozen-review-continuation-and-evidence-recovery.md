# Frozen-review continuation and evidence recovery

Use when a relay delivery resumes in a new/compacted session after immutable-review workers were launched but their verdicts are not present in recoverable conversation or process state.

## Evidence rule

- “Review launched” is not review evidence. A delegation ID, progress summary, or old promise that results will return cannot substitute for the reviewers' actual terminal verdicts.
- Search the relevant session lineage and inspect recoverable background state. If the exact verdict is absent, classify that review lane as **not completed**, even when the frozen digest itself remains valid.
- Never infer CLEAN from elapsed time, vanished workers, no returned findings, or a previous assistant summary.

## Safe continuation sequence

1. Restore the explicit delivery checklist; session-local todo state may not survive lineage changes.
2. Re-read the immutable manifest and independently authenticate its manifest hash, binary diff hash/size, source-capture hash/size, recorded HEAD/base/branch, path inventory, regenerated binary diff, and candidate tree.
3. If authentication fails, stop with `SNAPSHOT_DRIFT` or artifact-integrity failure. Do not restart reviews against an uncertain boundary.
4. If authentication passes but verdicts are unrecoverable, restart every required independent read-only lane against the same immutable boundary. Give each reviewer a unique reconstruction directory outside the source repository.
5. Require start and closing boundary checks in every verdict. A reviewer self-report without the closing check is incomplete.
6. Give every reviewer an explicit **closure budget**. Reserve the final tool calls for: stop all candidate-facing work, write the formal report body, run the complete end verifier, finalize only the END attestation without another candidate read, hash the report, and verify the sidecar. A practical rule is to finish exploratory review by roughly call 20–25 and reserve at least the final **four assistant tool turns** (not merely four individual tool invocations) for report → END → sidecar → sidecar verification. Existing authenticated full-suite evidence may be cited while focused probes are rerun; do not spend the closure reserve repeating a long suite solely for redundancy.

   Treat the reserve as a hard stop, not a suggestion:
   - Keep a call ledger from START onward and reassess it after every test/probe batch.
   - Batch independent reads and searches in one parallel turn; avoid serial source-reading once the required seams and line references are known.
   - Once the required focused/full suites, mandatory negative probes, and final reconstructed-candidate integrity check are complete, stop exploring low-severity possibilities and begin closure immediately.
   - Prewrite the complete report with a unique `END_PENDING` slot. The END wrapper may run the exact verifier and then replace that slot using only its captured verifier result; after the verifier's last source read, it must perform no further candidate/live-source reads. This preserves the required order (report first, END second) while allowing the sealed report to contain truthful END evidence before hashing.
   - Make the sidecar operation the final tool turn: calculate the report SHA-256, write `<report>.sha256`, and verify it against the report without touching the candidate.
   - If the runtime announces that no tool calls remain before report/END/sidecar are complete, return `INCOMPLETE`; green tests and zero findings do not compensate for an unsealed lane.
7. Tell reviewers that a discovered blocker does not end the task: they must still run end closure and seal a `BLOCKED` report. Conversely, if the closure reserve has begun, stop adding probes and close the lane; an unsealed long investigation is `INCOMPLETE`, not a stronger review.
8. While reviews run, perform only independent read-only preparation. Do not stage, write markers, fetch into boundary-bearing refs, commit, or otherwise change evidence that later gates depend on.
9. Any candidate-byte fix invalidates all in-flight or prior verdicts: rerun affected/full gates, create a new immutable digest, and restart all required final lanes.

## Delayed, filtered, and superseded reviewer returns

- A provider safety-filter response is **not a reviewer verdict**, even when the delegation framework marks the task completed. Re-dispatch that lane with an authorized local code-quality / policy-conformance framing, narrower acceptance criteria, or an approved fallback provider. Do not count it as CLEAN or BLOCKED-by-code.
- Exception for an already-blocked immutable generation: if another fully closed lane has independently produced an accepted Critical/High/Medium blocker, the operator may close the old generation as `BLOCKED` without spending another reviewer run solely to fill the filtered lane. Record that lane explicitly as `INCOMPLETE — PROVIDER FILTERED`, preserve no inferred verdict, authenticate the main BLOCKED disposition with its own digest sidecar, and require the repaired generation to regain complete coverage for every required lane. This exception saves obsolete review work; it never permits delivery or a CLEAN label.
- Avoid unnecessary hostile/exploit wording in reviewer prompts when the task is local defensive verification. Keep the same concrete checks—non-launch sentinels, credential-read ordering, ownership/CAS, fail-closed decisions—but frame them as code quality and policy conformance.
- A delayed report for an older frozen digest cannot satisfy a newer digest's review lane. Its findings are still actionable signals: inspect whether the implicated bytes and claim remain in the current candidate. If so, block the current candidate, fix in a new digest, and cite the older report as finding provenance; if not, record why it is superseded.
- A report that says it could not run the closing verifier or could not write the requested evidence file is incomplete. Preserve the returned details, but restart or independently close the lane before counting it. Reproducible Critical/High/Medium findings from such a lane still block that exact generation; they do **not** turn the lane into an end-closed verdict.
- If several incomplete lanes nevertheless produce reproducible blockers, the main operator may seal a consolidated `BLOCKED / INCOMPLETE` disposition and SHA sidecar for the obsolete generation. Record each lane's missing closing ceremony, finding severity, evidence path, and immutable boundary identity. This closes the generation as unsafe; it does not manufacture missing reviewer verdicts or permit freeze.
- When a stale-digest finding causes a new fix, do not modify the old frozen bytes. Save a main-operator BLOCKED report beside that digest, make the fix in a new isolated candidate, rerun full gates, and freeze again.

## Provider routing and authentication recovery

A reviewer provider's authentication or region refusal is an **incomplete lane**, not a code verdict. Recover it without weakening boundary or reviewer identity requirements:

1. Check the reviewer's own auth status, then run one minimal non-mutating inference probe. A CLI may report an account as logged in while its cached OAuth session still cannot refresh; successful account metadata is not proof that inference works.
2. Verify the **actual outbound country seen by the provider path**. Distinguish four different facts: the VPN application is running, a tunnel is connected, the selected exit region, and the process's observed egress region. Only the last two explain a provider geo-block.
3. Do not infer that a named VPN product is disconnected from unrelated `scutil --nc list` services. On macOS, clients such as NordVPN can use their own network extension and need not appear as the Passepartout/network-service entries being listed. If the user says NordVPN is in use, inspect that client or state only the independently observed egress; never relabel disconnected Passepartout profiles as NordVPN status.
4. A VPN can be connected yet still exit in a blocked country. Say `observed egress is <country>` rather than `the VPN is off` unless the VPN client itself proves that claim.
5. Changing a system-wide VPN endpoint affects the user's other traffic. Obtain explicit permission, record the original endpoint/state without credentials, switch only to a provider-supported endpoint, verify egress, run the bounded reviewer retries, and restore the original state afterward.
6. OAuth browser consent, passwords, MFA, and pasted authorization codes are human steps. The agent may launch the documented login command and wait, but must not click consent/password dialogs, type secrets, or preserve OAuth URLs, state parameters, codes, tokens, or account identifiers in review artifacts.
7. After the user completes login or routing recovery, verify auth/egress again and perform one fresh immutable read-only review attempt. If it succeeds, stop retrying. If it fails for the same infrastructure reason, preserve the failure metadata and keep delivery blocked rather than substituting a different model/provider without an explicit lane waiver.
8. Provider-only retries may write outside the sealed view, but they must not mutate candidate bytes. Re-run the lane's immutable candidate closure and source END verifier before accepting any recovered report.

## Reporting discipline

State explicitly that commit/push/PR remain blocked until the restarted lanes return valid verdicts. Distinguish:

- snapshot authenticated;
- review dispatched;
- review verdict received and boundary-closed;
- all required lanes CLEAN.

Only the last state unlocks the next litmus/finalization stage.
