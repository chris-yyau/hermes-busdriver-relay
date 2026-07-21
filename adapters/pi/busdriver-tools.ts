import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { relative, resolve } from "path";
import { execFileSync } from "child_process";
import { randomUUID } from "crypto";

// No `fs` import, deliberately, and this is the whole of the r30 fix. Every path-based call —
// lstatSync/readFileSync/mkdirSync/openSync — resolves its pathname AGAIN at the moment it acts,
// so a parent swapped for a symlink after our check redirected the effect out of the repo, and
// O_NOFOLLOW never helped because it constrains only the last component. Node has no openat(2)
// (no dir_fd on fs.open, no *at family, no descriptor on fs.Dir), so the traversal cannot be made
// race-free here at all. It moves to busdriver-fs-broker.py, which has the syscall and walks every
// component bound to its parent's descriptor. Not importing `fs` is what keeps that true: there is
// no filesystem call in this file to get the ordering wrong in.
//
// r31 finishes the same thought for git. `execFileSync("git", ...)` was PATH-resolved — the
// ambient PATH chose the binary that then ran against the repo — and argv-shaped, so every call
// site was one string away from a mutating verb, guarded only by a denylist of env names somebody
// had to remember to keep complete. Read-only git inspection is a question about the repository
// root, and the root is the broker's descriptor, so it moves there too: the broker holds the
// wrapper-authenticated retained git and a fixed table of argv templates, and this file names a
// VERB. The only child process left in this file is the broker itself.

const AUTHORITY_FLAGS = {
  finalization_allowed: false,
  commit_allowed: false,
  push_allowed: false,
  pr_allowed: false,
  merge_allowed: false,
  marker_write_allowed: false,
  deploy_allowed: false,
  release_allowed: false,
  publish_allowed: false,
};

const MAX_BD_FILE_BYTES = 256 * 1024;

const FORBIDDEN_MARKER_PARTS = [
  ".git",
  ".claude",
  ".opencode",
  "litmus-passed.local",
  "pr-review-passed.local",
  "skip-litmus.local",
  "skip-ultra-oracle.local",
  "blueprint-review-passed.local",
];

// GIT_ENV_DENYLIST used to live here: ~24 env names scrubbed before handing the rest of our own
// environment to git. A denylist over an inherited env is the wrong shape — it has to name every
// variable that could matter, so the one nobody thought of is inherited — and it is gone with the
// execFileSync it protected. The broker builds git's whole environment from a fixed table instead
// (see git_env()), which is an allowlist by construction and cannot be short.

const COMMON_SECRET_PATH = /(^|\/)(\.env(?:\..*)?|\.npmrc|\.pypirc|\.netrc|\.aws\/credentials|\.aws\/config|\.ssh\/[^/]+|\.docker\/config\.json|(?:gcloud|\.config\/gcloud)\/application_default_credentials\.json|id_rsa|id_ed25519|[^/]*\.(?:pem|key|p12|pfx))(\/|$)/i;
const GIT_IGNORE_RULE_PATH = /(^|\/)\.gitignore$/i;

function repoRoot(): string {
  return resolve(process.env.BD_REPO_ROOT || process.cwd());
}

type BrokerRequest =
  | { op: "read"; root: "repo" | "run"; rel: string }
  | { op: "write" | "append"; root: "repo" | "run"; rel: string; content: string }
  | { op: "git"; root: "repo" | "run"; verb: GitVerb; rel: string };

// The verbs the broker will run, and the only git this file can reach. There is no argv here to
// smuggle a subcommand through: the broker owns the templates, so this side names an intent.
type GitVerb = "check_ignore" | "status" | "branch" | "head" | "diff" | "diff_name_only" | "diff_stat" | "log";

// Non-git effects contain no child process, so their short deadline bounds a wedged broker. Git
// gets a separate deadline longer than the Python broker's 120s deadline plus its 5s group reap:
// killing Python first would skip that cleanup and orphan Git. Neither deadline is caller-tunable.
const BROKER_TIMEOUT_MS = 5_000;
const BROKER_GIT_TIMEOUT_MS = 130_000;

// One `python3 -I broker` per effect. A long-lived broker holding the root fd would save the
// process spawn, but a draft run makes tens of these, not thousands, and a daemon buys a lifecycle
// and a socket to get wrong. Upgrade if a real run is ever measured to care.
function broker(request: BrokerRequest): any {
  const python = process.env.BD_BROKER_PYTHON;
  const script = process.env.BD_BROKER_SCRIPT;
  // Default-deny: unconfigured means uncontained, and uncontained is exactly what r30 removed.
  if (!python || !script) throw new Error("broker_unconfigured");
  // The broker's env carries the root paths and NOTHING else — it is handed no credential it could
  // leak, and the roots are named by label in the request so this side cannot widen its own reach.
  // Every value here was resolved by the trusted parent wrapper. BD_BROKER_GIT is deliberately not
  // among them any more: naming git's pathname in the environment made the executable the broker
  // ran a value that a writer of this process's environment could choose. The broker resolves it
  // from its own frozen root-owned table.
  const env: Record<string, string> = {};
  for (const key of ["BD_BROKER_ROOT_REPO", "BD_BROKER_ROOT_RUN"]) {
    const value = process.env[key];
    if (value) env[key] = value;
  }
  let raw: string;
  try {
    raw = execFileSync(python, ["-I", script], {
      input: JSON.stringify(request),
      encoding: "utf8",
      env,
      maxBuffer: 8 * 1024 * 1024,
      timeout: request.op === "git" ? BROKER_GIT_TIMEOUT_MS : BROKER_TIMEOUT_MS,
    });
  } catch {
    throw new Error("broker_unavailable");
  }
  const response = JSON.parse(raw);
  if (!response || response.ok !== true) throw new Error(String(response?.error || "broker_refused"));
  return response;
}

function runRel(abs: string): string {
  // The event log and the artifact are the adjacent escape: same pathname pattern, same swap, so
  // they are contained under the run root rather than written by absolute path.
  const root = process.env.BD_BROKER_ROOT_RUN;
  if (!root) throw new Error("broker_unconfigured");
  const rel = relative(root, resolve(abs));
  if (rel === "" || rel === ".." || rel.startsWith("../") || rel.startsWith("/")) {
    throw new Error("run_root_escape");
  }
  return rel;
}

function log(kind: string, payload: Record<string, unknown>) {
  const logPath = process.env.PI_BD_EVENT_LOG || resolve(process.cwd(), ".pi-bd-events.jsonl");
  broker({ op: "append", root: "run", rel: runRel(logPath), content: JSON.stringify({ ts: Date.now(), kind, ...payload }) + "\n" });
}

function asText(obj: Record<string, unknown>) {
  return [{ type: "text" as const, text: JSON.stringify(obj, null, 2) }];
}

function normalizeRel(abs: string, root: string): string {
  // No backslash fold. On POSIX `a\b.py` is ONE file whose name contains a backslash; folding it
  // to `a/b.py` matched it against an allowlist of `a/*.py` the real file was never in — and it
  // folded the character away before scopeTokenRejected() could ever see it.
  const rel = relative(root, abs);
  if (rel === "" || rel === ".." || rel.startsWith("../") || rel.startsWith("/")) {
    throw new Error("path_escape");
  }
  return rel;
}

// assertNoSymlinkEscape() used to live here: it walked the components with existsSync/lstatSync
// and then every caller re-resolved the same string. That is the check/use pair itself, and a
// tighter or repeated version of it is still a pathname check — which is why r30 deletes it rather
// than hardening it. Symlink refusal is now the broker's, where the check IS the use: the fd it
// returns is the directory it proved.

function escapeRegExpChar(ch: string): string {
  // `?` is intentionally handled as a single-segment glob wildcard in globToRegExp()
  // before this literal regex escaping path is reached.
  return /[.+^${}()|[\]\\]/.test(ch) ? `\\${ch}` : ch;
}

function safePath(input: string): { rel: string } {
  // Policy only — marker paths, secret paths, ignore-rule freezes. Containment is the broker's:
  // this returns a repo-relative name, never an absolute path for a caller to act on.
  const root = repoRoot();
  const rel = normalizeRel(resolve(root, input), root);
  const relLower = rel.toLowerCase();
  const parts = relLower.split("/");
  if (parts.some((p) => FORBIDDEN_MARKER_PARTS.includes(p))) {
    throw new Error(`protected_path_blocked:${rel}`);
  }
  if (/(^|\/)(skip-[^/]*\.local|[^/]*passed[^/]*\.local)(\/|$)/i.test(rel)) {
    throw new Error(`trusted_marker_path_blocked:${rel}`);
  }
  // Freeze ignore-rule semantics for the whole Pi run: broad write scopes must
  // not let Pi edit .gitignore first, then read/write a formerly ignored file.
  if (GIT_IGNORE_RULE_PATH.test(rel)) {
    throw new Error(`git_ignore_rule_path_blocked:${rel}`);
  }
  return { rel };
}

// Parity with scope_token_rejected() in the gate and the two draft wrappers. POSIX pathnames are
// bytes up to a NUL, so LF/CR/VT/FF, the C1 block, U+2028/U+2029 and a backslash are all creatable
// filename characters that the glob metacharacters read inconsistently. They are refused outright
// rather than matched: a declared scope is a reviewed list, and no legitimate entry needs one.
// eslint-disable-next-line no-control-regex
const SCOPE_FORBIDDEN_CHARS = /[\u0000-\u001f\u007f-\u009f\u2028\u2029\\]/;

function scopeTokenRejected(value: string): boolean {
  return SCOPE_FORBIDDEN_CHARS.test(value);
}

function globToRegExp(glob: string): RegExp {
  let pattern = "";
  for (let i = 0; i < glob.length;) {
    if (glob.slice(i, i + 3) === "**/") {
      pattern += "(?:[\\s\\S]*/)?";
      i += 3;
    } else if (glob.slice(i, i + 2) === "**") {
      // [\s\S]*, not .*: `.` skips newlines, so an exclude of `**/secrets/**` failed to match a
      // path with an embedded newline. `**` means "any characters", newlines included.
      pattern += "[\\s\\S]*";
      i += 2;
    } else if (glob[i] === "*") {
      pattern += "[^/]*";
      i += 1;
    } else if (glob[i] === "?") {
      pattern += "[^/]";
      i += 1;
    } else {
      pattern += escapeRegExpChar(glob[i]);
      i += 1;
    }
  }
  // JavaScript `$` also matches immediately before a final line terminator. A negative
  // any-character lookahead is the actual end-of-input assertion, independent of flags.
  return new RegExp(`^${pattern}(?![\\s\\S])`);
}

// The scope arrives as a JSON array, and the reason is the transport it replaces. A newline-joined
// list has no way to say "this pattern contains a newline" — so a single declared scope of
// `safe\n**` did not arrive as one rejected pattern, it arrived as TWO: `safe`, and `**`. The
// wrapper's own scope_token_rejected() refused the character, and the split then re-admitted it as
// a separate, unrejected, repo-wide allow. The framing has to be unambiguous BEFORE anything
// interprets it, and JSON is: a newline inside an element stays inside that element, where
// scopeTokenRejected() can see it and refuse it.
function parseScopeList(value: string | undefined): string[] {
  if (!value) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    // Default-deny: an unparseable scope is not an empty scope, it is an unknown one. Returning []
    // from here would make pathAllowed() deny everything, which is the direction we want, but the
    // throw says so out loud rather than leaving it to a caller's convention.
    throw new Error("scope_transport_invalid");
  }
  if (!Array.isArray(parsed)) throw new Error("scope_transport_invalid");
  for (const item of parsed) {
    if (typeof item !== "string") throw new Error("scope_transport_invalid");
    // Rejected at the boundary, not at match time: a pattern carrying a control character is a
    // reviewed list that does not say what it appears to say.
    if (scopeTokenRejected(item)) throw new Error("scope_pattern_rejected");
  }
  return (parsed as string[]).filter((s) => s !== "");
}

function isCommonSecretPath(rel: string): boolean {
  return COMMON_SECRET_PATH.test(rel);
}

function isGitIgnored(rel: string): boolean {
  // A broker refusal throws, and every caller of this treats a throw as a denial — so an
  // unanswerable ignore question denies the path rather than admitting it, as it always did.
  return broker({ op: "git", root: "repo", verb: "check_ignore", rel }).ignored === true;
}

function scopeMatches(rel: string, pat: string): boolean {
  // Strict, full-string, and identical for allow and deny patterns alike. Rejection answers false
  // in BOTH directions, so pathAllowed() rejects the path outright rather than letting a rejected
  // path read as "nothing denies it, therefore allow it".
  if (scopeTokenRejected(rel) || scopeTokenRejected(pat)) return false;
  return rel === pat || globToRegExp(pat).test(rel);
}

function pathAllowed(rel: string): boolean {
  if (scopeTokenRejected(rel)) return false;
  const allow = parseScopeList(process.env.PI_BD_ALLOWED_WRITES);
  if (!allow.length) return false;
  return allow.some((pat) => scopeMatches(rel, pat));
}

function pathDenied(rel: string): boolean {
  const deny = parseScopeList(process.env.PI_BD_DENIED_WRITES);
  return deny.some((pat) => scopeMatches(rel, pat));
}

function git(verb: GitVerb): string {
  // `-c core.fsmonitor=false` used to be prepended here, because core.fsmonitor names a command
  // git runs on index refresh and it is settable from the REPO-LOCAL config — the very repo an
  // untrusted draft worker just wrote to. It is the broker's fixed argv now, alongside
  // core.hooksPath and GIT_OPTIONAL_LOCKS, where no caller can forget it.
  return broker({ op: "git", root: "repo", verb, rel: "" }).output.trim();
}

function baseEnvelope(tool: string, extra: Record<string, unknown>) {
  return {
    schema: "pi-busdriver-tool-result/v0",
    tool,
    not_busdriver_native_claude_runtime: true,
    repo_root: repoRoot(),
    cwd: process.cwd(),
    mode: process.env.PI_BD_MODE || "readonly",
    ...extra,
    ...AUTHORITY_FLAGS,
  };
}

function authorityEnvelope() {
  return { ...AUTHORITY_FLAGS };
}

function currentBranch(): string {
  try { return git("branch"); } catch { return ""; }
}

function currentHead(): string {
  try { return git("head"); } catch { return ""; }
}

export default function(pi: ExtensionAPI) {
  pi.on("tool_call", async (event: any) => {
    log("tool_call_event", { toolName: event.toolName });
    return undefined;
  });

  pi.registerTool({
    name: "bd_status",
    label: "Busdriver-shaped status",
    description: "Read-only Busdriver-shaped repo status. Never authorizes mutation/finalization.",
    parameters: Type.Object({}),
    execute: async () => {
      log("execute", { toolName: "bd_status" });
      let status = "";
      try { status = git("status"); } catch (error: any) { status = `ERROR:${error.message}`; }
      return {
        content: asText(baseEnvelope("bd_status", {
          ok: true,
          read_only: true,
          mutation_allowed: false,
          branch: currentBranch(),
          head: currentHead(),
          status_short: status,
          busdriver_state_dir: process.env.BUSDRIVER_STATE_DIR || ".claude",
          busdriver_plugin_root_visible: Boolean(process.env.BUSDRIVER_PLUGIN_ROOT),
        })),
        details: { status },
      };
    },
  });

  pi.registerTool({
    name: "bd_read",
    label: "Busdriver-shaped read",
    description: "Read a small text file inside the repo root with Busdriver-style path guards.",
    parameters: Type.Object({ path: Type.String({ description: "Relative path inside the repo root" }) }),
    execute: async (_toolCallId, params: { path: string }) => {
      log("execute", { toolName: "bd_read", path: params.path });
      try {
        const { rel } = safePath(params.path);
        if (isCommonSecretPath(rel)) {
          return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: "common_secret_path_blocked", path: rel })), details: { denied: true } };
        }
        if (isGitIgnored(rel)) {
          return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: "gitignored_path_blocked", path: rel })), details: { denied: true } };
        }
        // The broker enforces the size bound on the descriptor it read, so the stat-then-read pair
        // that used to bound this is gone with every other pathname round trip.
        const content = broker({ op: "read", root: "repo", rel }).content;
        return {
          content: asText(baseEnvelope("bd_read", { ok: true, read_only: true, mutation_allowed: false, path: rel, content })),
          details: { path: rel, bytes: Buffer.byteLength(content, "utf8") },
        };
      } catch (error: any) {
        return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: error.message })), details: { denied: true } };
      }
    },
  });

  pi.registerTool({
    name: "bd_write_draft",
    label: "Busdriver-shaped draft write",
    description: "Draft-only write. Enforces scope.include, repo-root containment, operation_id, before_hash, after_hash, marker blocks, and symlink refusal.",
    parameters: Type.Object({
      path: Type.String({ description: "Relative output path inside declared scope.include" }),
      content: Type.String({ description: "Draft content to write" }),
      operation_id: Type.Optional(Type.String({ description: "Optional caller operation id" })),
    }),
    execute: async (_toolCallId, params: { path: string; content: string; operation_id?: string }) => {
      const operation_id = params.operation_id || randomUUID();
      log("execute", { toolName: "bd_write_draft", path: params.path, operation_id });
      const mode = process.env.PI_BD_MODE || "readonly";
      try {
        const { rel } = safePath(params.path);
        if (isCommonSecretPath(rel)) {
          return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: "common_secret_path_blocked", path: rel, operation_id })), details: { denied: true } };
        }
        if (isGitIgnored(rel)) {
          return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: "gitignored_path_blocked", path: rel, operation_id })), details: { denied: true } };
        }
        if (mode !== "draft") {
          return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: "readonly_mode", mode, operation_id })), details: { denied: true } };
        }
        if (pathDenied(rel)) {
          return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: "path_excluded", path: rel, operation_id })), details: { denied: true } };
        }
        if (!pathAllowed(rel)) {
          return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: "path_not_allowlisted", path: rel, operation_id })), details: { denied: true } };
        }
        const contentBytes = Buffer.byteLength(params.content, "utf8");
        if (contentBytes > MAX_BD_FILE_BYTES) {
          return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: "write_size_limit", path: rel, operation_id, bytes: contentBytes })), details: { denied: true } };
        }
        // One brokered op, not four pathname round trips: the parent walk, the before hash, the
        // create/truncate/write and the after hash all happen under descriptors the broker proved
        // and holds. Both hashes are of the inode it wrote — not of whatever the name resolved to
        // by the time a second call got there.
        const written = broker({ op: "write", root: "repo", rel, content: params.content });
        const { before_hash, after_hash } = written;
        const audit = { toolName: "bd_write_draft", path: rel, operation_id, before_hash, after_hash, bytes: contentBytes };
        log("write_audit", audit);
        return {
          content: asText(baseEnvelope("bd_write_draft", {
            ok: true,
            read_only: false,
            mutation_allowed: true,
            draft_mutation_only: true,
            needs_busdriver_review: true,
            path: rel,
            operation_id,
            before_hash,
            after_hash,
            bytes: contentBytes,
          })),
          details: audit,
        };
      } catch (error: any) {
        return { content: asText(baseEnvelope("bd_write_draft", { ok: false, read_only: false, denied: true, reason: error.message, operation_id })), details: { denied: true } };
      }
    },
  });

  pi.registerTool({
    name: "bd_bash",
    label: "Busdriver-shaped argv-only bash",
    description: "argv-only and allowlist-only command wrapper. No shell expansion, no arbitrary bash -c, no network by default, no finalization or marker writes.",
    parameters: Type.Object({
      cmd: Type.String({ description: "Allowed executable name, e.g. git" }),
      args: Type.Array(Type.String(), { description: "Argument vector. This is argv-only; shell strings and bash -c are rejected." }),
    }),
    execute: async (_toolCallId, params: { cmd: string; args: string[] }) => {
      log("execute", { toolName: "bd_bash", cmd: params.cmd, args: params.args });
      const cmd = params.cmd;
      const args = params.args || [];
      const joined = [cmd, ...args].join(" ");
      const pathspecSeparator = args.indexOf("--");
      const controlArgs = pathspecSeparator >= 0 ? args.slice(0, pathspecSeparator) : args;
      const controlJoined = [cmd, ...controlArgs].join(" ");
      const finalizationForbidden = /\b(commit|push|merge|rebase|reset|tag|checkout|switch|deploy|release|publish|curl|wget|rm|chmod|chown)\b|bash\s+-c/i;
      const markerForbidden = /litmus-passed\.local|pr-review-passed\.local|skip-[^\s/]+\.local/i;
      if (finalizationForbidden.test(controlJoined) || markerForbidden.test(joined) || cmd === "bash" || cmd === "sh") {
        return { content: asText(baseEnvelope("bd_bash", { ok: false, read_only: true, denied: true, reason: "argv_or_finalization_blocked", cmd, args })), details: { denied: true } };
      }
      // The allowlist is now a MAPPING, not a permission slip. It used to decide whether `args`
      // was safe and then hand that same `args` to execFileSync — so the allowlist had to be
      // exhaustively right about argv, forever. Here a match only selects a broker verb whose argv
      // the broker owns; nothing the caller typed is ever executed. An unmatched argv is refused
      // exactly as before, so the tool contract is unchanged.
      const allowedGit: Array<{ args: string[]; verb: GitVerb }> = [
        { args: ["-c", "core.fsmonitor=false", "status", "--porcelain=v1", "--untracked-files=all"], verb: "status" },
        { args: ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv"], verb: "diff" },
        { args: ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv", "--name-only"], verb: "diff_name_only" },
        { args: ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv", "--stat"], verb: "diff_stat" },
        { args: ["rev-parse", "HEAD"], verb: "head" },
        { args: ["log", "--oneline"], verb: "log" },
      ];
      const allowed = cmd === "git"
        ? allowedGit.find((pat) => pat.args.length === args.length && pat.args.every((v, i) => v === args[i]))
        : undefined;
      if (!allowed) {
        return { content: asText(baseEnvelope("bd_bash", { ok: false, read_only: true, denied: true, reason: "command_not_allowlisted", cmd, args })), details: { denied: true } };
      }
      try {
        const output = git(allowed.verb);
        return { content: asText(baseEnvelope("bd_bash", { ok: true, read_only: true, mutation_allowed: false, cmd, args, output })), details: { output } };
      } catch (error: any) {
        return { content: asText(baseEnvelope("bd_bash", { ok: false, read_only: true, cmd, args, error: error.message })), details: { error: true } };
      }
    },
  });

  pi.registerTool({
    name: "bd_artifact",
    label: "Busdriver-shaped final draft artifact",
    description: "Writes the structured Pi draft artifact. It can only end in needs_busdriver_review or blocked, never done/finalized.",
    parameters: Type.Object({
      status: Type.String({ description: "needs_busdriver_review or blocked" }),
      summary: Type.String(),
      files_changed: Type.Array(Type.String()),
      tests_run: Type.Array(Type.Object({ name: Type.String(), command: Type.String(), ok: Type.Boolean() })),
      blocked_actions: Type.Array(Type.Object({ action: Type.String(), reason: Type.String() })),
      limitations: Type.Array(Type.String()),
    }),
    execute: async (_toolCallId, params: { status: string; summary: string; files_changed: string[]; tests_run: any[]; blocked_actions: any[]; limitations: string[] }) => {
      log("execute", { toolName: "bd_artifact", status: params.status });
      const status = params.status === "blocked" ? "blocked" : "needs_busdriver_review";
      if (!["needs_busdriver_review", "blocked"].includes(params.status)) {
        return { content: asText(baseEnvelope("bd_artifact", { ok: false, read_only: true, denied: true, reason: "invalid_status", requested_status: params.status })), details: { denied: true } };
      }
      const artifact = {
        schema: "pi-busdriver-result/v0",
        worker: "pi",
        mode: "mutating_draft",
        ok: status === "needs_busdriver_review",
        status,
        repo: repoRoot(),
        branch: currentBranch(),
        base_head: process.env.HERMES_BASE_HEAD || "",
        post_head: currentHead(),
        changed_files: params.files_changed,
        files_changed: params.files_changed,
        tests_run: params.tests_run || [],
        review_findings: [],
        blockers: status === "blocked" ? (params.blocked_actions || []).map((b: any) => b.reason || b.action || "blocked") : [],
        authority: authorityEnvelope(),
        artifacts: [],
        event_log: [process.env.PI_BD_EVENT_LOG || ""].filter(Boolean),
        summary: params.summary,
        blocked_actions: params.blocked_actions || [],
        limitations: params.limitations || [],
        not_busdriver_native_claude_runtime: true,
        ...AUTHORITY_FLAGS,
      };
      const artifactPath = process.env.PI_BD_ARTIFACT_PATH || resolve(process.cwd(), "pi-result.json");
      broker({ op: "write", root: "run", rel: runRel(artifactPath), content: JSON.stringify(artifact, null, 2) + "\n" });
      return { content: asText(baseEnvelope("bd_artifact", { ok: true, read_only: true, mutation_allowed: false, status, artifact_path: artifactPath })), details: { artifact_path: artifactPath } };
    },
  });
}
