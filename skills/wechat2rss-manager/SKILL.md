# wechat2rss-manager

Manage a self-hosted Wechat2RSS service safely through the `w2r` CLI.

## Use when
- You need to query service/account/subscription/article/feed state.
- You need low-risk subscription operations (`add-id`, `add-url`, `pause`, `resume`).
- You need feed or proxy URL generation.

## Safety rules
- Never print real `W2R_TOKEN` or `W2R_PROXY_SECRET`.
- Prefer `w2r init --from-env` or `--token-stdin`; avoid token in shell history.
- Keep `w2r config get` redacted by default; only use `--show-secrets` with explicit approval and `W2R_ALLOW_SHOW_SECRETS=1`.
- Avoid destructive commands by default (`subs delete` must require `--yes`).
- Do not run server-side Docker/DB/data-directory operations from this skill.

## Typical workflow
1. Validate CLI and config:
   - `w2r --help`
   - `w2r service version`
2. Read-only checks:
   - `w2r accounts list`
   - `w2r subs list --page 1 --size 20`
   - `w2r articles query --after YYYYMMDD --content 0`
3. Feed checks:
   - `w2r feed all --format xml --print-url`
   - `w2r feed channel <biz_id> --format json --print-url`
4. Optional low-risk write checks:
   - `w2r subs add-url <article_url>` (run once)
   - `w2r subs pause <biz_id>` then `w2r subs resume <biz_id>`

## Output expectations
- Show concise pass/fail by command group.
- Redact sensitive values in logs and examples.
- If blocked by missing config or secrets, stop and report exact missing item.
