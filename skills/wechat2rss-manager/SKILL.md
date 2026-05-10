---
name: wechat2rss-manager
description: Manage a self-hosted Wechat2RSS service through the local `w2r` CLI. Use this skill whenever the user asks to inspect Wechat2RSS service health, accounts, subscriptions, articles, feed URLs, proxy URLs, or safe subscription operations. Prefer this skill over raw HTTP, curl, database, Docker, or direct config-file access, even if the user does not explicitly mention the `w2r` command.
---

# wechat2rss-manager

Manage a self-hosted Wechat2RSS service safely through the local `w2r` CLI.

## Core assumptions
- The user wants the local CLI workflow, not direct API calls.
- `w2r` should be on `PATH`; first verify with `command -v w2r` and `w2r --help`.
- Config may come from `~/.config/w2r/config.json` or env vars; do not read or print the config file.
- Treat token, proxy secret, feed URLs with `k=...`, and raw config output as sensitive.

## Hard safety rules
- Only call the `w2r` CLI for Wechat2RSS operations.
- Do not call the service with `curl` or raw HTTP.
- Do not read, cat, grep, or print `~/.config/w2r/config.json`.
- Never print real `W2R_TOKEN`, `W2R_PROXY_SECRET`, or unredacted feed token URLs.
- Do not use `w2r config get --show-secrets` during agent execution.
- Do not use `--show-token-url` during agent execution.
- Do not run server-side Docker, database, volume, or data-directory operations from this skill.
- Before destructive operations, show the intended command and get explicit user confirmation.
- `w2r subs delete` must include `--yes`, so require explicit confirmation immediately before running it.

## Preflight
Run these before service work:

```bash
command -v w2r
w2r --help
```

If `w2r` is missing, recommend one of these local install paths:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install git+https://github.com/devon-kong/wechat2rss.git
```

or, if `pipx` is installed:

```bash
pipx install git+https://github.com/devon-kong/wechat2rss.git
```

## Config setup
Prefer env/stdin methods so real tokens do not enter shell history.

Env-based setup:

```bash
export W2R_BASE_URL="https://rss.example.com"
export W2R_TOKEN="..."
w2r init --from-env
```

Stdin token setup:

```bash
printf '%s\n' "$W2R_TOKEN" | w2r init --base-url "https://rss.example.com" --token-stdin
```

If config is missing, stop and report exactly which field is missing. Do not ask the user to paste secrets into chat.

Use a non-default config path only when the user asks for it or when running env-only smoke checks:

```bash
w2r --config /tmp/not-exist-w2r.json service --help
```

## Read-only workflows
Use read-only commands first:

```bash
w2r service version
w2r accounts list
w2r subs list --page 1 --size 20
w2r articles query --after YYYYMMDD --content 0
```

Article queries should default to `--content 0` to avoid large or sensitive output unless the user explicitly asks for full content.

## Feed and proxy workflows
Default feed URL output is safe because `k` is redacted:

```bash
w2r feed all --format xml --print-url
w2r feed channel <biz_id> --format json --print-url
```

For proxy URLs:

```bash
w2r proxy img "https://example.com/image.jpg" --print-url
w2r proxy video "https://example.com/video.mp4" --print-url
w2r proxy link "https://example.com/article" --print-url
```

Do not use proxy `--fetch` unless the user explicitly asks to fetch content.

## Write workflows
Low-risk writes still need a brief confirmation when they change subscriptions:

```bash
w2r subs add-url <article_url>
w2r subs add-id <biz_id>
w2r subs pause <biz_id>
w2r subs resume <biz_id>
```

For delete, first inspect, then ask for confirmation, then run:

```bash
w2r subs list --page 1 --size 20
w2r subs delete <biz_id> --yes
```

## Output format
Report concise command-group results:

```text
preflight passed
service check passed
accounts listed
subscriptions listed
feed URL redacted
blocked: missing W2R_TOKEN
```

When showing URLs or config-like output, redact sensitive query values as `***REDACTED***`.

## CLI reference
Use this as the complete command map. Prefer the safest command variant that answers the user's question.

### Global
```bash
w2r --help
w2r --config <path> <command> ...
```

`--config` selects a config file. Do not read the file directly; let `w2r` load it.

### init
Safe preferred setup:

```bash
w2r init --from-env
printf '%s\n' "$W2R_TOKEN" | w2r init --base-url "https://rss.example.com" --token-stdin
```

Full option map:

```bash
w2r init \
  --base-url "https://rss.example.com" \
  --token-stdin \
  --proxy-secret "$W2R_PROXY_SECRET" \
  --timeout 20 \
  --hmac-algo sha256
```

Avoid `--token <token>` because it can enter shell history. Mention it only as a compatibility path, not as the recommended agent action.

### service
```bash
w2r service version
w2r service version --json
```

Use `--json` when the user asks for machine-readable output or downstream scripting.

### accounts
```bash
w2r accounts list
w2r accounts list --json
```

Use `--json` for structured processing; otherwise keep human-readable output.

### subscriptions
Read-only:

```bash
w2r subs list --page 1 --size 50
w2r subs list --page 1 --size 20 --name "公众号名称"
w2r subs list --json
w2r subs opml
w2r subs opml --output subscriptions.opml
```

Low-risk writes, but still confirm intent before running:

```bash
w2r subs add-id <biz_id>
w2r subs add-url <article_url>
w2r subs pause <biz_id>
w2r subs resume <biz_id>
```

Destructive:

```bash
w2r subs delete <biz_id> --yes
```

Before delete, run a list/search command and ask the user to confirm the exact `biz_id`.

### articles
Default to metadata-only:

```bash
w2r articles query --content 0
w2r articles query --bid <biz_id> --content 0
w2r articles query --after YYYYMMDD --content 0
w2r articles query --before YYYYMMDD --content 0
w2r articles query --after YYYYMMDD --before YYYYMMDD --content 0
w2r articles query --json --content 0
```

Only use full content when explicitly requested:

```bash
w2r articles query --content 1
```

### config
Safe default:

```bash
w2r config get
```

This is redacted by default. Do not use this during normal agent execution:

```bash
w2r config get --show-secrets
```

`--show-secrets` requires `W2R_ALLOW_SHOW_SECRETS=1`, but the skill should still avoid it because the goal is operational safety, not secret inspection.

### feed
Print redacted feed URLs:

```bash
w2r feed all --format xml --print-url
w2r feed all --format json --print-url
w2r feed channel <biz_id> --format xml --print-url
w2r feed channel <biz_id> --format json --print-url
```

Fetch feed content to stdout or file:

```bash
w2r feed all --format xml
w2r feed all --format json
w2r feed all --format xml --output feed.xml
w2r feed channel <biz_id> --format xml --output channel.xml
```

Do not use:

```bash
w2r feed all --print-url --show-token-url
```

`--show-token-url` exposes the real feed token.

### proxy
Print proxy URLs:

```bash
w2r proxy img "https://example.com/image.jpg" --print-url
w2r proxy video "https://example.com/video.mp4" --print-url
w2r proxy link "https://example.com/article" --print-url
```

Fetch proxy results only when explicitly requested:

```bash
w2r proxy img "https://example.com/image.jpg" --fetch
w2r proxy video "https://example.com/video.mp4" --fetch --output video.mp4
w2r proxy link "https://example.com/article" --fetch --output article.html
```

Proxy commands require `W2R_PROXY_SECRET` or `proxy_secret` in config. If missing, stop and report that proxy signing is not configured.

## Safety classification
- Safe read-only: `--help`, `service version`, `accounts list`, `subs list`, `subs opml`, `articles query --content 0`, `config get`, `feed --print-url` with default redaction, `proxy --print-url`.
- Safe with output-size caution: `articles query --content 1`, feed fetch without `--print-url`, OPML export to file.
- Write requires confirmation: `subs add-id`, `subs add-url`, `subs pause`, `subs resume`.
- Destructive requires explicit confirmation: `subs delete <biz_id> --yes`.
- Prohibited in agent execution: raw HTTP, reading config files directly, `config get --show-secrets`, `feed all --show-token-url`.
