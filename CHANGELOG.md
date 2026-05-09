# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-05-10

### Added
- Package layout under `src/w2r/` and Python console script entrypoint `w2r`.
- CI workflow for Python 3.10-3.13 with tests, compile checks, and CLI smoke.
- Homebrew formula template and npm wrapper template.
- Security hardening for init flow: `--token-stdin` and `--from-env`.
- Secret redaction by default in `w2r config get`.
- Additional tests for proxy key behavior, config loading errors, config file mode, feed URL generation, and secret display guard.

### Changed
- README installation instructions now use install-from-git URLs before package registry release.
- `--show-secrets` now requires `W2R_ALLOW_SHOW_SECRETS=1`.
- Expanded CLI smoke coverage in CI to include `accounts/config/feed/proxy`.

### Removed
- Root-level `w2r.py` duplicate entrypoint to avoid logic drift.
