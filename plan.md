# wechat2rss status

## Current release
- `v0.1.0` GitHub Release is published: https://github.com/devon-kong/wechat2rss/releases/tag/v0.1.0
- Release tag commit: `e95cab7c8192f13d73032bce03b4503dbbc38efc`
- `main` includes the Homebrew Formula sha256 update.
- Formula update commit verified by CI: `159aa189fe16e177fef02c6b4daa2040e57f43b5`

## Verified local install/use
- Existing local `w2r` command is available at `/Users/devon/.local/bin/w2r`.
- `w2r --help` and subcommand help smoke tests passed.
- Env-only config smoke passed with only `W2R_BASE_URL` and `W2R_TOKEN`.
- Feed URL redaction smoke passed: default `--print-url` output redacts `k`.
- Isolated venv install from GitHub passed:
  - `python -m pip install git+https://github.com/devon-kong/wechat2rss.git`

## Deferred distribution tasks
These are intentionally paused and should not block local use.

1. PyPI publish
   - `twine` is installed in `/tmp/w2r-release-venv`.
   - `python -m twine check /tmp/w2r-release-dist/*` passed.
   - Blocked on PyPI API token.
   - Do not paste token into chat; use `TWINE_USERNAME=__token__` and `TWINE_PASSWORD`.

2. npm publish
   - `w2r-cli` currently returns 404 on npm registry, so the name appears available.
   - Blocked on `npm login` or an npm token.
   - Note: npm package is a Node wrapper around local Python, so user experience depends on Python 3.10+ already being installed.

3. Homebrew tap publish
   - `Formula/w2r.rb` has real `v0.1.0` tarball sha256.
   - `devon-kong/homebrew-tap` was not found during the check.
   - Blocked on confirming creation of a public tap repo and pushing the formula there.
