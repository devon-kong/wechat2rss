# w2r

`w2r` 是一个用于管理自建 Wechat2RSS 服务的命令行工具。

- 语言: Python 3.10+
- 依赖: 标准库（无第三方运行时依赖）
- 默认配置路径: `~/.config/w2r/config.json`

## 功能

- 微信账号管理: 列表、可用状态、风控状态、下次检查时间
- 订阅管理: 列表、搜索、add-id、add-url、delete、pause、resume、OPML 导出
- 文章查询: 全量/按公众号/按 before-after，支持 `--content 0|1`
- 配置读取: `config get`（默认脱敏）
- Feed: 单公众号/合集 XML 和 JSON
- 代理: `img/video/link` URL 生成，支持可选 `--fetch`

## 安装

### 1) pip/pipx（推荐）

```bash
pipx install w2r-cli
# 或
python3 -m pip install w2r-cli
```

### 2) Homebrew（通过 tap）

本仓库提供 formula 模板: `Formula/w2r.rb`。

发布后可通过你自己的 tap 安装（示例）：

```bash
brew tap your-org/your-tap
brew install w2r
```

说明：`Formula/w2r.rb` 里 `url` 和 `sha256` 需要在发布新版本后更新为真实 release 产物。

### 3) npm（Node 包装器）

```bash
npm install -g w2r-cli
```

说明：npm 包内部会调用本机 `python3` 执行 `w2r`，所以仍需 Python 3.10+。

## 快速开始

### 初始化

推荐方式 1（环境变量）：

```bash
export W2R_BASE_URL="https://rss.example.com"
export W2R_TOKEN="your-rss-token"
export W2R_PROXY_SECRET="your-proxy-secret"
w2r init --from-env
```

推荐方式 2（stdin，避免命令行明文 token）：

```bash
printf '%s\n' "your-rss-token" | w2r init \
  --base-url "https://rss.example.com" \
  --token-stdin \
  --proxy-secret "your-proxy-secret"
```

兼容方式（不推荐，token 会进入 shell history）：

```bash
w2r init --base-url "https://rss.example.com" --token "your-rss-token"
```

### 常用命令

```bash
w2r service version
w2r accounts list
w2r subs list --page 1 --size 10
w2r articles query --after 20260501 --content 0
w2r feed all --format xml --print-url
w2r proxy img "https://example.com/test.jpg"
```

## 安全说明

- 不要提交任何真实 token 或 secret。
- `w2r config get` 默认脱敏；如确需明文，必须显式加 `--show-secrets`。
- `w2r config get --show-secrets` 需要额外设置 `W2R_ALLOW_SHOW_SECRETS=1` 才会生效。
- 删除订阅必须加 `--yes`，避免误删。
- 不建议把真实 token 放在命令历史里，优先使用配置文件或安全注入方式。

## 开发

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
pytest
python -m py_compile w2r.py src/w2r/cli.py
```

## 版本管理

- 当前版本在 `src/w2r/__init__.py` 与 `pyproject.toml` 中保持一致。
- 发布时建议：
  1. bump 版本号
  2. 打 tag（如 `v0.1.0`）
  3. 发布 GitHub Release
  4. 更新 Homebrew Formula 的 `url/sha256`

## 许可证

MIT
