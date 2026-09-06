# AGENTS.md — onchain-volume-tracker

## Rules
1. **No personal data, ever.** No names, addresses, emails, phones, resumes,
   or job-search material. No tokens, keys, or credentials of any kind.
2. **Channel IDs resolve from the local registry.** Never hardcode a Discord
   server or channel ID in this repo. The registry
   (`~/.hermes/studio/projects.yaml`) is local-only and stays out of git.
3. **Gate before push.** `bash tools/check_pii.sh --all` must pass. The
   pre-push hook enforces `--all`; CI enforces `--all`.
4. **Owner is `0x-m-dev`.** Never push to any other account/remote.
   Identity is repo-local (global stays untouched for other work):
   `git config user.name 0x-m-dev` +
   `git config user.email <id>+0x-m-dev@users.noreply.github.com`.
   Noreply email keeps personal addresses out of public history.
5. **Carry context in the project, not the chat.** Read `SPEC.md`,
   `PROJECT.yaml`, `PROJECT_STATE.md`, and this file before significant work.
   After meaningful work, update `PROJECT_STATE.md` with verified state,
   decisions, next actions, blockers, and timestamp.
6. **Do not schedule incomplete collection.** launchd/cron and Discord
   webhook delivery need explicit approval after tests and a live run.

## Layout
- `src/tracker/` — CLI, collector, analyzer, report, SQLite helpers
- `tests/` — pytest regression suite
- `tools/` — PII gate, README freshness, hook installer
- `.github/workflows/pii-scan.yml` — CI gate
- `launchd/` — plist template only; do not load until scheduling is approved
