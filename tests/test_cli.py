from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from w2r.cli import (
    W2RError,
    add_query,
    build_parser,
    cmd_config_get,
    load_config,
    normalize_base_url,
    redact_secrets,
    resolve_init_config,
)


def test_normalize_base_url_ok() -> None:
    assert normalize_base_url("https://rss.example.com/") == "https://rss.example.com"


def test_normalize_base_url_invalid() -> None:
    with pytest.raises(W2RError):
        normalize_base_url("rss.example.com")


def test_add_query_merge() -> None:
    out = add_query("https://a.com/path?a=1", {"b": 2})
    assert "a=1" in out
    assert "b=2" in out


def test_redact_secrets_nested() -> None:
    payload = {
        "data": {
            "settings": {
                "RSS_TOKEN": "real-token",
                "RSS_PROXY_SECRET": "real-secret",
                "RSS_HOST": "127.0.0.1:8080",
            }
        }
    }
    redacted = redact_secrets(payload)
    settings = redacted["data"]["settings"]
    assert settings["RSS_TOKEN"] == "***REDACTED***"
    assert settings["RSS_PROXY_SECRET"] == "***REDACTED***"
    assert settings["RSS_HOST"] == "127.0.0.1:8080"


def test_load_config_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "base_url": "https://old.example.com",
                "token": "old",
                "proxy_secret": "old-secret",
                "timeout": 20,
                "hmac_algo": "sha256",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("W2R_BASE_URL", "https://new.example.com")
    monkeypatch.setenv("W2R_TOKEN", "new-token")

    loaded = load_config(cfg_path)
    assert loaded["base_url"] == "https://new.example.com"
    assert loaded["token"] == "new-token"


def test_delete_requires_yes() -> None:
    parser = build_parser()
    args = parser.parse_args(["subs", "delete", "123"])
    assert args.yes is False


def test_init_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--from-env"])
    monkeypatch.setenv("W2R_BASE_URL", "https://rss.example.com")
    monkeypatch.setenv("W2R_TOKEN", "env-token")
    cfg = resolve_init_config(args)
    assert cfg["base_url"] == "https://rss.example.com"
    assert cfg["token"] == "env-token"


def test_init_token_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--base-url", "https://rss.example.com", "--token-stdin"])
    monkeypatch.setattr(sys, "stdin", StringIO("stdin-token\n"))
    cfg = resolve_init_config(args)
    assert cfg["token"] == "stdin-token"


def test_config_get_show_secrets_needs_env() -> None:
    class DummyClient:
        def get_json(self, path: str):
            return {"data": {"settings": {"RSS_TOKEN": "x"}}, "err": ""}

    parser = build_parser()
    args = parser.parse_args(["config", "get", "--show-secrets"])
    with pytest.raises(W2RError):
        cmd_config_get(DummyClient(), args)
