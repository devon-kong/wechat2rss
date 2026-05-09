#!/usr/bin/env python3
"""
w2r - A small CLI wrapper for a self-hosted Wechat2RSS service.

Python: 3.10+
Dependencies: standard library only.

Config default path:
  ~/.config/w2r/config.json

Example:
  w2r init --base-url https://rss.example.com --token YOUR_RSS_TOKEN --proxy-secret YOUR_RSS_PROXY_SECRET
  w2r accounts list
  w2r subs list --page 1 --size 50
  w2r subs add-url 'https://mp.weixin.qq.com/s/xxx'
  w2r articles query --after 20260501 --content 0
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_CONFIG = Path.home() / ".config" / "w2r" / "config.json"
SENSITIVE_FIELD_NAMES = {
    "token",
    "proxy_secret",
    "rss_token",
    "rss_proxy_secret",
    "rss_secret",
    "bot_server_key",
}


class W2RError(Exception):
    pass


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def load_config(path: Path) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
        except json.JSONDecodeError as exc:
            raise W2RError(f"Invalid config JSON: {path}: {exc}") from exc

    # Environment variables override file config, useful for CI/Agent runtime.
    cfg["base_url"] = os.environ.get("W2R_BASE_URL", cfg.get("base_url", ""))
    cfg["token"] = os.environ.get("W2R_TOKEN", cfg.get("token", ""))
    cfg["proxy_secret"] = os.environ.get("W2R_PROXY_SECRET", cfg.get("proxy_secret", ""))
    cfg["timeout"] = int(os.environ.get("W2R_TIMEOUT", cfg.get("timeout", 20)))
    cfg["hmac_algo"] = os.environ.get("W2R_HMAC_ALGO", cfg.get("hmac_algo", "sha256"))

    if not cfg.get("base_url"):
        raise W2RError(
            "base_url is missing. Set W2R_BASE_URL or run: "
            "w2r init --base-url https://your-domain --token YOUR_RSS_TOKEN"
        )
    if not cfg.get("token"):
        raise W2RError(
            "token is missing. Set W2R_TOKEN or run: "
            "w2r init --base-url https://your-domain --token YOUR_RSS_TOKEN"
        )
    return cfg


def save_config(path: Path, cfg: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise W2RError("base_url must start with http:// or https://")
    return base_url


def add_query(url: str, params: Dict[str, Any]) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    for k, v in params.items():
        if v is not None:
            query[k] = str(v)
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def read_response(resp: urllib.response.addinfourl) -> Tuple[bytes, str]:
    content_type = resp.headers.get("content-type", "")
    return resp.read(), content_type


def request_url(
    url: str,
    *,
    method: str = "GET",
    timeout: int = 20,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[bytes, str]:
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return read_response(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise W2RError(f"HTTP {exc.code} {exc.reason}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise W2RError(f"Request failed: {exc}") from exc


def maybe_json(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def redact_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in obj.items():
            if key.lower() in SENSITIVE_FIELD_NAMES:
                out[key] = "***REDACTED***"
            else:
                out[key] = redact_secrets(value)
        return out
    if isinstance(obj, list):
        return [redact_secrets(item) for item in obj]
    return obj


def print_text_or_json(raw: bytes, as_json: bool = False) -> None:
    obj = maybe_json(raw)
    if as_json or isinstance(obj, (dict, list)):
        print_json(obj)
    else:
        print(obj)


def write_or_print(raw: bytes, output: Optional[str], content_type: str = "") -> None:
    if output:
        Path(output).write_bytes(raw)
        eprint(f"Saved to {output}")
        return
    # XML/JSON/text are safe to print. Binary proxy data should usually use --output.
    if content_type and not any(t in content_type.lower() for t in ["text", "xml", "json", "html"]):
        sys.stdout.buffer.write(raw)
    else:
        sys.stdout.write(raw.decode("utf-8", errors="replace"))


def redact_url_query_value(url: str, key: str, mask: str = "***REDACTED***") -> str:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if key in query:
        query[key] = mask
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def redact_url_token(url: str) -> str:
    return redact_url_query_value(url, "k")


def table(rows: List[Dict[str, Any]], columns: List[Tuple[str, str]]) -> None:
    if not rows:
        print("(empty)")
        return
    str_rows: List[List[str]] = []
    for row in rows:
        str_rows.append([str(row.get(key, "")) for key, _ in columns])
    headers = [title for _, title in columns]
    widths = [len(h) for h in headers]
    for r in str_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))

    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for r in str_rows:
        print(fmt.format(*r))


class W2RClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.base_url = normalize_base_url(cfg.get("base_url", ""))
        self.token = cfg.get("token", "")
        self.proxy_secret = cfg.get("proxy_secret", "")
        self.timeout = int(cfg.get("timeout", 20))
        self.hmac_algo = cfg.get("hmac_algo", "sha256")
        if not self.token:
            raise W2RError("token is missing in config. Run: w2r init --base-url ... --token ...")

    def build(self, path: str, params: Optional[Dict[str, Any]] = None, auth: bool = True) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        q = dict(params or {})
        if auth:
            q["k"] = self.token
        return add_query(url, q)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, auth: bool = True) -> Tuple[bytes, str]:
        return request_url(self.build(path, params, auth=auth), timeout=self.timeout)

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None, auth: bool = True) -> Any:
        raw, _ = self.get(path, params, auth)
        obj = maybe_json(raw)
        if isinstance(obj, dict) and obj.get("err"):
            raise W2RError(f"Wechat2RSS error: {obj.get('err')}")
        return obj

    def proxy_key(self, target_url: str) -> str:
        if not self.proxy_secret:
            raise W2RError("proxy_secret is required for proxy URL generation. Set W2R_PROXY_SECRET or config.proxy_secret.")
        algo = self.hmac_algo.lower()
        if algo not in hashlib.algorithms_available:
            raise W2RError(f"Unsupported HMAC algorithm: {algo}")
        digestmod = getattr(hashlib, algo, None)
        if digestmod is None:
            digestmod = lambda data=b"": hashlib.new(algo, data)  # type: ignore[misc]
        return hmac.new(
            self.proxy_secret.encode("utf-8"),
            target_url.encode("utf-8"),
            digestmod,
        ).hexdigest()[:8]

    def proxy_url(self, kind: str, target_url: str) -> str:
        key = self.proxy_key(target_url)
        endpoint = {"img": "img-proxy", "video": "video-proxy", "link": "link-proxy"}[kind]
        # Docs show img/video as ?u=...&k=...; link docs are less explicit, but use u consistently here.
        return add_query(self.base_url + f"/{endpoint}", {"u": target_url, "k": key})


def require_yes(args: argparse.Namespace, message: str) -> None:
    if not getattr(args, "yes", False):
        raise W2RError(message + " Add --yes to confirm.")


def _read_stdin_secret(label: str) -> str:
    value = sys.stdin.readline().rstrip("\r\n")
    if not value:
        raise W2RError(f"{label} is empty from stdin")
    return value


def resolve_init_config(args: argparse.Namespace) -> Dict[str, Any]:
    if args.token and args.token_stdin:
        raise W2RError("--token and --token-stdin cannot be used together")

    base_url = args.base_url or ""
    token = args.token or ""
    proxy_secret = args.proxy_secret or ""

    if args.from_env:
        if not base_url:
            base_url = os.environ.get("W2R_BASE_URL", "")
        if not token and not args.token_stdin:
            token = os.environ.get("W2R_TOKEN", "")
        if not proxy_secret:
            proxy_secret = os.environ.get("W2R_PROXY_SECRET", "")

    if args.token_stdin:
        token = _read_stdin_secret("token")

    if not base_url:
        raise W2RError("base_url is required. Set --base-url or W2R_BASE_URL with --from-env.")
    if not token:
        raise W2RError("token is required. Use --token, --token-stdin, or W2R_TOKEN with --from-env.")

    return {
        "base_url": normalize_base_url(base_url),
        "token": token,
        "proxy_secret": proxy_secret,
        "timeout": args.timeout,
        "hmac_algo": args.hmac_algo,
    }


def cmd_init(args: argparse.Namespace) -> None:
    cfg = resolve_init_config(args)
    save_config(Path(args.config), cfg)
    print(f"Config saved: {args.config}")


def cmd_accounts_list(client: W2RClient, args: argparse.Namespace) -> None:
    obj = client.get_json("/login/list")
    if args.json:
        print_json(obj)
        return
    rows = obj.get("data", []) if isinstance(obj, dict) else []
    table(rows, [
        ("id", "账号ID"),
        ("name", "昵称"),
        ("available", "可用"),
        ("needCheck", "风控中"),
        ("waitTime", "下次检查时间"),
    ])


def cmd_subs_list(client: W2RClient, args: argparse.Namespace) -> None:
    params = {"page": args.page, "size": args.size, "name": args.name}
    obj = client.get_json("/list", params)
    if args.json:
        print_json(obj)
        return
    rows = obj.get("data", []) if isinstance(obj, dict) else []
    total = obj.get("meta", {}).get("total") if isinstance(obj, dict) else None
    if total is not None:
        print(f"total: {total}")
    table(rows, [("id", "公众号ID"), ("name", "公众号名称"), ("link", "订阅地址")])


def cmd_subs_add_id(client: W2RClient, args: argparse.Namespace) -> None:
    obj = client.get_json(f"/add/{args.id}")
    print_json(obj)


def cmd_subs_add_url(client: W2RClient, args: argparse.Namespace) -> None:
    obj = client.get_json("/addurl", {"url": args.url})
    print_json(obj)


def cmd_subs_delete(client: W2RClient, args: argparse.Namespace) -> None:
    require_yes(args, f"Deleting subscription {args.id} is destructive.")
    obj = client.get_json(f"/del/{args.id}")
    print_json(obj)


def cmd_subs_pause_resume(client: W2RClient, args: argparse.Namespace, status: bool) -> None:
    obj = client.get_json(f"/pause/{args.id}", {"status": "true" if status else "false"})
    print_json(obj)


def cmd_subs_opml(client: W2RClient, args: argparse.Namespace) -> None:
    raw, content_type = client.get("/opml")
    write_or_print(raw, args.output, content_type)


def cmd_articles_query(client: W2RClient, args: argparse.Namespace) -> None:
    params = {
        "bid": args.bid,
        "before": args.before,
        "after": args.after,
        "content": args.content,
    }
    obj = client.get_json("/api/query", params)
    if args.json:
        print_json(obj)
        return
    rows = obj.get("data", []) if isinstance(obj, dict) else []
    print(f"total: {len(rows)}")
    table(rows, [
        ("biz_id", "公众号ID"),
        ("biz_name", "公众号"),
        ("title", "标题"),
        ("created", "发布时间"),
        ("desc", "摘要"),
    ])


def cmd_config_get(client: W2RClient, args: argparse.Namespace) -> None:
    obj = client.get_json("/config")
    if args.show_secrets and os.environ.get("W2R_ALLOW_SHOW_SECRETS") != "1":
        raise W2RError("Refusing to show secrets. Set W2R_ALLOW_SHOW_SECRETS=1 and retry with --show-secrets.")
    print_json(obj if args.show_secrets else redact_secrets(obj))


def cmd_version(client: W2RClient, args: argparse.Namespace) -> None:
    raw, _ = client.get("/version", auth=False)
    print_text_or_json(raw, args.json)


def cmd_feed_channel(client: W2RClient, args: argparse.Namespace) -> None:
    suffix = args.format
    path = f"/feed/{args.id}.{suffix}"
    url = client.build(path, auth=False)
    if args.print_url:
        print(url)
        return
    raw, content_type = client.get(path, auth=False)
    write_or_print(raw, args.output, content_type)


def cmd_feed_all(client: W2RClient, args: argparse.Namespace) -> None:
    suffix = args.format
    path = f"/feed/all.{suffix}"
    url = client.build(path, auth=True)
    if args.print_url:
        print(url if args.show_token_url else redact_url_token(url))
        return
    raw, content_type = client.get(path, auth=True)
    write_or_print(raw, args.output, content_type)


def cmd_proxy(client: W2RClient, args: argparse.Namespace, kind: str) -> None:
    url = client.proxy_url(kind, args.url)
    if args.print_url or not args.fetch:
        print(url)
        return
    raw, content_type = request_url(url, timeout=client.timeout)
    write_or_print(raw, args.output, content_type)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="w2r", description="CLI for self-hosted Wechat2RSS")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help=f"config path, default: {DEFAULT_CONFIG}")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create config file")
    p_init.add_argument("--base-url", default=None, help="Wechat2RSS base URL, e.g. https://rss.example.com")
    p_init.add_argument("--token", default=None, help="RSS_TOKEN (avoid shell history leakage; prefer --token-stdin)")
    p_init.add_argument("--token-stdin", action="store_true", help="read RSS_TOKEN from stdin")
    p_init.add_argument("--from-env", action="store_true", help="read missing fields from W2R_BASE_URL/W2R_TOKEN/W2R_PROXY_SECRET")
    p_init.add_argument("--proxy-secret", default="", help="RSS_PROXY_SECRET, needed for proxy URL generation")
    p_init.add_argument("--timeout", type=int, default=20)
    p_init.add_argument("--hmac-algo", default="sha256", help="HMAC algorithm for proxy signing, default: sha256")
    p_init.set_defaults(func=lambda client, args: cmd_init(args), no_client=True)

    p_accounts = sub.add_parser("accounts", help="WeChat account operations")
    acc_sub = p_accounts.add_subparsers(dest="accounts_cmd", required=True)
    p_acc_list = acc_sub.add_parser("list", help="list WeChat accounts")
    p_acc_list.add_argument("--json", action="store_true")
    p_acc_list.set_defaults(func=cmd_accounts_list)

    p_subs = sub.add_parser("subs", help="subscription operations")
    subs_sub = p_subs.add_subparsers(dest="subs_cmd", required=True)

    p_subs_list = subs_sub.add_parser("list", help="list subscriptions")
    p_subs_list.add_argument("--page", type=int, default=1)
    p_subs_list.add_argument("--size", type=int, default=50)
    p_subs_list.add_argument("--name", default=None, help="filter by account name")
    p_subs_list.add_argument("--json", action="store_true")
    p_subs_list.set_defaults(func=cmd_subs_list)

    p_add_id = subs_sub.add_parser("add-id", help="add subscription by WeChat public account ID")
    p_add_id.add_argument("id")
    p_add_id.set_defaults(func=cmd_subs_add_id)

    p_add_url = subs_sub.add_parser("add-url", help="add subscription by an article URL")
    p_add_url.add_argument("url")
    p_add_url.set_defaults(func=cmd_subs_add_url)

    p_delete = subs_sub.add_parser("delete", help="delete subscription by ID")
    p_delete.add_argument("id")
    p_delete.add_argument("--yes", action="store_true", help="confirm destructive operation")
    p_delete.set_defaults(func=cmd_subs_delete)

    p_pause = subs_sub.add_parser("pause", help="pause crawling by ID")
    p_pause.add_argument("id")
    p_pause.set_defaults(func=lambda client, args: cmd_subs_pause_resume(client, args, True))

    p_resume = subs_sub.add_parser("resume", help="resume crawling by ID")
    p_resume.add_argument("id")
    p_resume.set_defaults(func=lambda client, args: cmd_subs_pause_resume(client, args, False))

    p_opml = subs_sub.add_parser("opml", help="export OPML")
    p_opml.add_argument("--output", "-o", default=None)
    p_opml.set_defaults(func=cmd_subs_opml)

    p_articles = sub.add_parser("articles", help="article query operations")
    art_sub = p_articles.add_subparsers(dest="articles_cmd", required=True)
    p_query = art_sub.add_parser("query", help="query articles")
    p_query.add_argument("--bid", default=None, help="WeChat public account ID")
    p_query.add_argument("--before", default=None, help="YYYYMMDD")
    p_query.add_argument("--after", default=None, help="YYYYMMDD")
    p_query.add_argument("--content", choices=["0", "1"], default="0", help="include full content: 1 yes, 0 no; default 0")
    p_query.add_argument("--json", action="store_true")
    p_query.set_defaults(func=cmd_articles_query)

    p_config = sub.add_parser("config", help="read Wechat2RSS config; no write support")
    cfg_sub = p_config.add_subparsers(dest="config_cmd", required=True)
    p_cfg_get = cfg_sub.add_parser("get", help="GET /config")
    p_cfg_get.add_argument(
        "--show-secrets",
        action="store_true",
        help="show sensitive values (requires W2R_ALLOW_SHOW_SECRETS=1; default: redacted)",
    )
    p_cfg_get.set_defaults(func=cmd_config_get)

    p_service = sub.add_parser("service", help="service metadata")
    svc_sub = p_service.add_subparsers(dest="service_cmd", required=True)
    p_ver = svc_sub.add_parser("version", help="GET /version")
    p_ver.add_argument("--json", action="store_true")
    p_ver.set_defaults(func=cmd_version)

    p_feed = sub.add_parser("feed", help="feed operations")
    feed_sub = p_feed.add_subparsers(dest="feed_cmd", required=True)
    p_feed_channel = feed_sub.add_parser("channel", help="fetch or print a single channel feed")
    p_feed_channel.add_argument("id", help="public account ID or encrypted feed ID if RSS_ENC_FEED_ID is enabled")
    p_feed_channel.add_argument("--format", choices=["xml", "json"], default="xml")
    p_feed_channel.add_argument("--print-url", action="store_true")
    p_feed_channel.add_argument("--output", "-o", default=None)
    p_feed_channel.set_defaults(func=cmd_feed_channel)

    p_feed_all = feed_sub.add_parser("all", help="fetch or print all-in-one feed")
    p_feed_all.add_argument("--format", choices=["xml", "json"], default="xml")
    p_feed_all.add_argument("--print-url", action="store_true")
    p_feed_all.add_argument(
        "--show-token-url",
        action="store_true",
        help="print raw URL with token when used with --print-url",
    )
    p_feed_all.add_argument("--output", "-o", default=None)
    p_feed_all.set_defaults(func=cmd_feed_all)

    p_proxy = sub.add_parser("proxy", help="proxy URL generation/fetching")
    proxy_sub = p_proxy.add_subparsers(dest="proxy_cmd", required=True)
    for kind in ["img", "video", "link"]:
        pp = proxy_sub.add_parser(kind, help=f"generate/fetch {kind} proxy URL")
        pp.add_argument("url", help="target URL to proxy")
        pp.add_argument("--print-url", action="store_true", help="print proxy URL only")
        pp.add_argument("--fetch", action="store_true", help="fetch proxy result instead of only printing URL")
        pp.add_argument("--output", "-o", default=None)
        pp.set_defaults(func=(lambda k: (lambda client, args: cmd_proxy(client, args, k)))(kind))

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if getattr(args, "no_client", False):
            args.func(None, args)
        else:
            cfg = load_config(Path(args.config))
            client = W2RClient(cfg)
            args.func(client, args)
        return 0
    except W2RError as exc:
        eprint(f"Error: {exc}")
        return 2
    except KeyboardInterrupt:
        eprint("Interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
