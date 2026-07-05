import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { appendFileSync, closeSync, constants, existsSync, lstatSync, mkdirSync, openSync, readFileSync, writeFileSync } from "fs";
import { dirname, relative, resolve } from "path";
import { execFileSync } from "child_process";
import { createHash, randomUUID } from "crypto";

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

const GIT_ENV_DENYLIST = [
  "GIT_DIR",
  "GIT_WORK_TREE",
  "GIT_INDEX_FILE",
  "GIT_COMMON_DIR",
  "GIT_OBJECT_DIRECTORY",
  "GIT_ALTERNATE_OBJECT_DIRECTORIES",
  "GIT_EXTERNAL_DIFF",
  "GIT_DIFF_OPTS",
  "GIT_CONFIG_GLOBAL",
  "GIT_CONFIG_SYSTEM",
  "GIT_CONFIG_NOSYSTEM",
  "GIT_LITERAL_PATHSPECS",
  "GIT_GLOB_PATHSPECS",
  "GIT_NOGLOB_PATHSPECS",
  "GIT_ICASE_PATHSPECS",
  "GIT_TRACE",
  "GIT_TRACE2",
  "GIT_TRACE2_EVENT",
  "GIT_TRACE2_PERF",
  "GIT_ASKPASS",
  "GIT_SSH_COMMAND",
  "GIT_SSH",
  "GIT_PROXY_COMMAND",
  "GIT_EXEC_PATH",
];

const COMMON_SECRET_PATH = /(^|\/)(\.env(?:\..*)?|\.npmrc|\.pypirc|\.netrc|\.aws\/credentials|\.aws\/config|\.ssh\/[^/]+|\.docker\/config\.json|(?:gcloud|\.config\/gcloud)\/application_default_credentials\.json|id_rsa|id_ed25519|[^/]*\.(?:pem|key|p12|pfx))(\/|$)/i;
const GIT_IGNORE_RULE_PATH = /(^|\/)\.gitignore$/i;

function repoRoot(): string {
  return resolve(process.env.BD_REPO_ROOT || process.cwd());
}

function hashFile(path: string): string | null {
  if (!existsSync(path)) return null;
  const h = createHash("sha256");
  h.update(readFileSync(path));
  return h.digest("hex");
}

function log(kind: string, payload: Record<string, unknown>) {
  const logPath = process.env.PI_BD_EVENT_LOG || resolve(process.cwd(), ".pi-bd-events.jsonl");
  mkdirSync(dirname(logPath), { recursive: true });
  appendFileSync(logPath, JSON.stringify({ ts: Date.now(), kind, ...payload }) + "\n");
}

function asText(obj: Record<string, unknown>) {
  return [{ type: "text" as const, text: JSON.stringify(obj, null, 2) }];
}

function normalizeRel(abs: string, root: string): string {
  const rel = relative(root, abs).split("\\").join("/");
  if (rel === "" || rel.startsWith("..") || rel.startsWith("/")) {
    throw new Error("path_escape");
  }
  return rel;
}

function assertNoSymlinkEscape(abs: string, rel: string, root: string) {
  // Symlink refusal is explicit: even an existing final symlink is blocked.
  const parts = rel.split("/").filter(Boolean);
  let cur = root;
  for (const part of parts) {
    cur = resolve(cur, part);
    if (existsSync(cur) && lstatSync(cur).isSymbolicLink()) {
      throw new Error(`symlink_escape_refused:${part}`);
    }
  }
  if (existsSync(abs) && lstatSync(abs).isSymbolicLink()) {
    throw new Error("symlink_escape_refused:target");
  }
}

function escapeRegExpChar(ch: string): string {
  // `?` is intentionally handled as a single-segment glob wildcard in globToRegExp()
  // before this literal regex escaping path is reached.
  return /[.+^${}()|[\]\\]/.test(ch) ? `\\${ch}` : ch;
}

function safePath(input: string): { abs: string; rel: string } {
  const root = repoRoot();
  const abs = resolve(root, input);
  const rel = normalizeRel(abs, root);
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
  assertNoSymlinkEscape(abs, rel, root);
  return { abs, rel };
}

function globToRegExp(glob: string): RegExp {
  let pattern = "";
  for (let i = 0; i < glob.length;) {
    if (glob.slice(i, i + 3) === "**/") {
      pattern += "(?:.*/)?";
      i += 3;
    } else if (glob.slice(i, i + 2) === "**") {
      pattern += ".*";
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
  return new RegExp(`^${pattern}$`);
}

function splitList(value: string | undefined): string[] {
  return (value || "")
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function sanitizedGitEnv(): Record<string, string | undefined> {
  const env = { ...process.env };
  for (const key of GIT_ENV_DENYLIST) {
    delete env[key];
  }
  return env;
}

function isCommonSecretPath(rel: string): boolean {
  return COMMON_SECRET_PATH.test(rel);
}

function isGitIgnored(rel: string): boolean {
  try {
    execFileSync("git", ["-c", "core.fsmonitor=false", "check-ignore", "-q", "--", rel], { cwd: repoRoot(), env: sanitizedGitEnv(), stdio: ["ignore", "ignore", "ignore"] });
    return true;
  } catch (error: any) {
    if (error && error.status === 1) return false;
    throw new Error("git_ignore_check_failed");
  }
}

function pathAllowed(rel: string): boolean {
  const allow = splitList(process.env.PI_BD_ALLOWED_WRITES);
  if (!allow.length) return false;
  return allow.some((pat) => rel === pat || globToRegExp(pat).test(rel));
}

function pathDenied(rel: string): boolean {
  const deny = splitList(process.env.PI_BD_DENIED_WRITES);
  return deny.some((pat) => rel === pat || globToRegExp(pat).test(rel));
}

function git(args: string[]): string {
  const safeArgs = args[0] === "-c" && args[1] === "core.fsmonitor=false" ? args : ["-c", "core.fsmonitor=false", ...args];
  return execFileSync("git", safeArgs, { cwd: repoRoot(), env: sanitizedGitEnv(), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
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
  try { return git(["branch", "--show-current"]); } catch { return ""; }
}

function currentHead(): string {
  try { return git(["rev-parse", "HEAD"]); } catch { return ""; }
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
      try { status = git(["-c", "core.fsmonitor=false", "status", "--porcelain=v1", "--untracked-files=all"]); } catch (error: any) { status = `ERROR:${error.message}`; }
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
        const { abs, rel } = safePath(params.path);
        if (isCommonSecretPath(rel)) {
          return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: "common_secret_path_blocked", path: rel })), details: { denied: true } };
        }
        if (isGitIgnored(rel)) {
          return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: "gitignored_path_blocked", path: rel })), details: { denied: true } };
        }
        const stat = lstatSync(abs);
        if (stat.size > MAX_BD_FILE_BYTES) {
          return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: "read_size_limit", path: rel })), details: { denied: true } };
        }
        const content = readFileSync(abs, "utf8");
        if (Buffer.byteLength(content, "utf8") > MAX_BD_FILE_BYTES) {
          return { content: asText(baseEnvelope("bd_read", { ok: false, read_only: true, denied: true, reason: "read_size_limit", path: rel })), details: { denied: true } };
        }
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
        const { abs, rel } = safePath(params.path);
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
        const before_hash = hashFile(abs);
        mkdirSync(dirname(abs), { recursive: true });
        assertNoSymlinkEscape(abs, rel, repoRoot());
        const writeFlags = constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC | (constants.O_NOFOLLOW || 0);
        let fd: number | null = null;
        try {
          fd = openSync(abs, writeFlags, 0o600);
          writeFileSync(fd, params.content, "utf8");
        } finally {
          if (fd !== null) closeSync(fd);
        }
        const after_hash = hashFile(abs);
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
      const allowedGit = [
        ["-c", "core.fsmonitor=false", "status", "--porcelain=v1", "--untracked-files=all"],
        ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv"],
        ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv", "--name-only"],
        ["-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv", "--stat"],
        ["rev-parse", "HEAD"],
        ["log", "--oneline"],
      ];
      const allowed = cmd === "git" && allowedGit.some((pat) => pat.length === args.length && pat.every((v, i) => v === args[i]));
      if (!allowed) {
        return { content: asText(baseEnvelope("bd_bash", { ok: false, read_only: true, denied: true, reason: "command_not_allowlisted", cmd, args })), details: { denied: true } };
      }
      try {
        const output = execFileSync(cmd, args, { cwd: repoRoot(), env: sanitizedGitEnv(), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
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
      mkdirSync(dirname(artifactPath), { recursive: true });
      writeFileSync(artifactPath, JSON.stringify(artifact, null, 2) + "\n", "utf8");
      return { content: asText(baseEnvelope("bd_artifact", { ok: true, read_only: true, mutation_allowed: false, status, artifact_path: artifactPath })), details: { artifact_path: artifactPath } };
    },
  });
}
