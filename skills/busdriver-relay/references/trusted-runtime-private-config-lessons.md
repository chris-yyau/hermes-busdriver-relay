# Trusted runtime and private agent configuration lessons

Use this note when a relay-owned adapter launches a provider CLI whose executable or runtime dependency must be authenticated and whose user configuration may contain plugins/packages.

## Authenticate the exact executable you invoke

A digest allowlist is insufficient if discovery uses `shutil.which()` and the adapter later trusts whichever binary appears first on a sanitized or guard-prefixed `PATH`. Bind both of these values in the trusted-runtime manifest:

- canonical absolute executable path;
- SHA-256 digest of that exact file.

At runtime, read and hash the pinned path, reject missing/unreadable/digest-mismatched files, and invoke that same absolute path. Do not resolve a different executable from `PATH` after validation. Add a contract test that compares the embedded path and digest with the manifest.

For script launchers that depend on another runtime (for example, a Pi launcher requiring Node), authenticate the dependency actually executed, not only the outer launcher tree.

## Build a minimum private config

Copying a user's entire provider settings file into an isolated HOME can activate packages, extensions, plugins, hooks, or startup behavior and defeat isolation. Prefer a new mode-0700 HOME/config tree containing only the credential artifact required for authentication. Pass model/provider explicitly on the command line instead of inheriting defaults.

For Pi, the durable safe pattern is:

1. create a private config directory;
2. copy only `auth.json` after rejecting symlinks and non-regular files;
3. do not copy `settings.json`, packages, or extensions;
4. set the provider CLI's HOME/config variables to the private tree;
5. keep command and diagnostic artifacts redacted;
6. test that a source settings file containing packages is not reproduced in the private config.

Apply the same principle to OpenCode or other provider CLIs: use plugin-free/pure mode when supported, isolate HOME/XDG directories, and copy only the minimum authentication material needed for a real smoke.

## Evidence lifecycle

A successful real-provider smoke proves only the exact snapshot and private-config/runtime pins used for that run. Any later adapter change—including a new regression test left RED—invalidates freeze/review/delivery readiness. Run targeted tests, full suite, static/security scans, and the relevant real smoke again before freezing a hash.
