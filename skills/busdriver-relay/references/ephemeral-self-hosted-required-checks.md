# Ephemeral self-hosted required-check rescue

Use this when a PR workflow has a required self-hosted job but the repository currently has no matching online runner, while a separate GitHub-hosted portable lane must remain independently meaningful. This is an operational rescue for a **trusted, exact candidate**, not a general way to execute untrusted pull-request code on a privileged machine.

## Diagnose queueing before changing code

A pending check is not necessarily a test failure. Establish which state exists:

1. Inspect the workflow job's `runs-on` labels.
2. Inspect the Actions run/job JSON. A job that remains `queued` with no steps differs from a running test.
3. Query the repository's registered runners and record name, status, busy state, OS, and labels.
4. Bind the evidence lane to the expected PR, commit OID, tree OID, and base OID.

Do not change the workflow merely because a required self-hosted job is queued. If the job intentionally represents a host-sealed contract, absence of runner capacity is an operational blocker. Preserve the separate GitHub-hosted portable subset; it proves portability but does not replace host-sealed coverage.

## Security boundary

Only attach an ephemeral runner when all of the following are true:

- the exact commit/tree was produced and reviewed locally;
- the PR does not contain untrusted fork code or attacker-controlled workflow changes;
- the runner uses the minimum repository scope and labels needed for one job;
- secrets are not printed, written into evidence files, or embedded in commands retained as artifacts;
- generated runner files, workspace, and logs live under the authorized external runtime root, never the repository, home, or system `/tmp`.

A self-hosted PR runner executes repository workflow bytes with host access. If trust is uncertain, stop rather than using the rescue.

## Provision an exact ephemeral runner

1. Read the current official `actions/runner` release metadata.
2. Select the asset matching the live OS/architecture.
3. Download under the authorized external runtime and verify the release-provided SHA-256 digest before extraction.
4. Preflight the runner environment **before registration**:
   - resolve the exact interpreter command used by the workflow;
   - verify required modules/tools and their versions;
   - when the job intentionally relies on a host-sealed environment, use the same tested venv/toolchain that produced local exact-tree evidence;
   - otherwise prefer making the workflow reproducible with pinned setup/install steps rather than relying on ambient host packages.
5. Request a short-lived registration token into a shell variable. Never print or persist it.
6. Configure with `--unattended --ephemeral`, a unique name, an isolated work directory, and the exact custom labels required by `runs-on`.
7. Start `run.sh` with the preflighted toolchain at the front of `PATH` when the workflow invokes an ambient command such as `python3`.

Example shape (redact repository-specific values and never log the token):

```bash
TOKEN="$(gh api --method POST repos/OWNER/REPO/actions/runners/registration-token --jq .token)"
./config.sh --unattended --ephemeral --replace \
  --url https://github.com/OWNER/REPO \
  --token "$TOKEN" \
  --name "exact-tree-ephemeral-UNIQUE" \
  --labels "trusted-runtime-label" \
  --work "_work-UNIQUE"
unset TOKEN
PATH="/authorized/exact-test-venv/bin:$PATH" ./run.sh
```

## Interpret results correctly

The runner listener can exit `0` after processing a job that GitHub marked **failed**. Runner lifecycle success proves only that the listener connected, accepted a job, and shut down cleanly. The authoritative result is the GitHub job/check conclusion.

After the listener exits:

1. Query the exact Actions run and job conclusion.
2. On failure, fetch failed step logs and classify setup/provisioning failure separately from test failure.
3. If retrying after a provisioning correction, request a fresh rerun of only failed jobs, clean the old isolated workspace, and register a new ephemeral runner instance. Do not reuse stale credentials.
4. Require the GitHub-reported check to pass and capture run/job URLs plus commit/tree binding.
5. Verify the ephemeral runner deregistered and that `.credentials`/`.runner` state is gone; remove rebuildable workspace/package data when no longer needed, retaining only sealed evidence logs and hashes.

## Common pitfalls

- `gh pr checks --watch` can wait indefinitely when no runner matches the labels. Inspect the job and runner inventory instead of treating this as slow tests.
- A green GitHub-hosted portable subset does not satisfy a separate required host-runtime check.
- Registering a runner without preflighting the workflow's interpreter/module resolution wastes the one-shot job and creates a misleading operational failure.
- Do not install dependencies opportunistically into the user's global interpreter. Use a dedicated verified environment or explicit pinned workflow provisioning.
- Do not infer job success from `run.sh` exit status.
- `--ephemeral` is not a cleanup substitute. Verify deregistration and remove the isolated workspace after evidence is sealed.
