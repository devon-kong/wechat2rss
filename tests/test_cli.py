from __future__ import annotations

import json
import re
import sys
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from w2r.cli import (
    W2RClient,
    W2RError,
    add_query,
    build_parser,
    cmd_config_get,
    cmd_feed_all,
    cmd_feed_channel,
    load_config,
    normalize_base_url,
    redact_secrets,
    save_config,
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
                "RSS_TOKEN": "example-token",
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


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(W2RError, match="base_url is missing"):
        load_config(tmp_path / "not-found.json")


def test_load_config_invalid_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"base_url": "https://rss.example.com", "token": "x"}), encoding="utf-8")
    monkeypatch.setenv("W2R_TIMEOUT", "bad-timeout")
    with pytest.raises(W2RError, match="Invalid W2R_TIMEOUT"):
        load_config(cfg_path)


def test_save_config_sets_private_mode(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    save_config(cfg_path, {"base_url": "https://rss.example.com", "token": "t"})
    assert cfg_path.exists()
    mode = cfg_path.stat().st_mode & 0o777
    assert mode == 0o600


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


def test_config_get_show_secrets_allowed_with_env(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class DummyClient:
        def get_json(self, path: str):
            return {"data": {"settings": {"RSS_TOKEN": "x"}}, "err": ""}

    parser = build_parser()
    args = parser.parse_args(["config", "get", "--show-secrets"])
    monkeypatch.setenv("W2R_ALLOW_SHOW_SECRETS", "1")
    cmd_config_get(DummyClient(), args)
    out = capsys.readouterr().out
    assert '"RSS_TOKEN": "x"' in out


def test_load_config_env_only_when_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "not-found.json"
    monkeypatch.setenv("W2R_BASE_URL", "https://rss.example.com")
    monkeypatch.setenv("W2R_TOKEN", "env-token")
    loaded = load_config(cfg_path)
    assert loaded["base_url"] == "https://rss.example.com"
    assert loaded["token"] == "env-token"


def test_proxy_key_deterministic_and_hex() -> None:
    client = W2RClient(
        {
            "base_url": "https://rss.example.com",
            "token": "abc",
            "proxy_secret": "secret",
            "hmac_algo": "sha256",
            "timeout": 20,
        }
    )
    key = client.proxy_key("https://example.com/a.jpg")
    assert len(key) == 8
    assert re.fullmatch(r"[0-9a-f]{8}", key)
    assert key == client.proxy_key("https://example.com/a.jpg")


def test_proxy_key_requires_secret() -> None:
    client = W2RClient(
        {
            "base_url": "https://rss.example.com",
            "token": "abc",
            "proxy_secret": "",
            "hmac_algo": "sha256",
            "timeout": 20,
        }
    )
    with pytest.raises(W2RError, match="proxy_secret is required"):
        client.proxy_key("https://example.com/a.jpg")


def test_proxy_key_invalid_algo() -> None:
    client = W2RClient(
        {
            "base_url": "https://rss.example.com",
            "token": "abc",
            "proxy_secret": "secret",
            "hmac_algo": "badalgo",
            "timeout": 20,
        }
    )
    with pytest.raises(W2RError, match="Unsupported HMAC algorithm"):
        client.proxy_key("https://example.com/a.jpg")


def test_feed_all_print_url_contains_auth(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(["feed", "all", "--format", "xml", "--print-url"])
    client = W2RClient(
        {
            "base_url": "https://rss.example.com",
            "token": "abc",
            "proxy_secret": "",
            "hmac_algo": "sha256",
            "timeout": 20,
        }
    )
    cmd_feed_all(client, args)
    out = capsys.readouterr().out.strip()
    assert out.startswith("https://rss.example.com/feed/all.xml?")
    assert "k=***REDACTED***" in out
    assert "k=abc" not in out


def test_feed_all_print_url_show_token_url(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(["feed", "all", "--format", "xml", "--print-url", "--show-token-url"])
    client = W2RClient(
        {
            "base_url": "https://rss.example.com",
            "token": "abc",
            "proxy_secret": "",
            "hmac_algo": "sha256",
            "timeout": 20,
        }
    )
    cmd_feed_all(client, args)
    out = capsys.readouterr().out.strip()
    assert out.startswith("https://rss.example.com/feed/all.xml?")
    assert "k=abc" in out


def test_feed_channel_print_url_no_auth(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(["feed", "channel", "123", "--format", "json", "--print-url"])
    client = W2RClient(
        {
            "base_url": "https://rss.example.com",
            "token": "abc",
            "proxy_secret": "",
            "hmac_algo": "sha256",
            "timeout": 20,
        }
    )
    cmd_feed_channel(client, args)
    out = capsys.readouterr().out.strip()
    assert out == "https://rss.example.com/feed/123.json"
