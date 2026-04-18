# Gemini WebAPI Gateway

[English](README.md) | 简体中文

Gemini WebAPI Gateway 是一个基于浏览器 Cookie 访问 Gemini 的私有部署网关，提供两种使用方式：

- 本地 CLI
- OpenAI 兼容 HTTP API

当前仓库重点是“能部署、能接入、能跑起来”，尤其偏向 Docker Compose 部署，而不是一个已经打磨完成的公共 SDK。

## 功能特性

- 从 `cookies.json` 读取 Cookie 初始化 Gemini 会话
- 提供 CLI 命令用于单轮提问、续聊、列出聊天、读取聊天和账号诊断
- 提供 OpenAI 兼容接口：
  - `GET /health`
  - `GET /v1/models`
  - `POST /v1/chat/completions`
- 支持非流式和 SSE 流式响应
- 支持 OpenAI 风格 `image_url` 图片输入
  - 支持 `data:image/...;base64,...`
  - 支持 `http(s)://...` 图片 URL
- 提供 Docker Compose 部署模板
- 通过挂载目录持久化 Cookie 缓存和刷新数据

## 当前范围与限制

- 目前只实现了 `/v1/models` 和 `/v1/chat/completions`
- 网关层目前仅通过 OpenAI 风格 `image_url` part 支持图片输入
- 许多 OpenAI 请求字段会被接受，但后续会被忽略
- `n` 必须等于 `1`
- 还没有实现 tool calling、function calling、结构化输出、音频输出、多模态输入
- OpenAI `messages` 会先被压平成一个文本 prompt，再发送给 Gemini
- 还没有实现 OpenAI 的文件上传接口
- `usage` 中的 token 统计是本地估算值，不是 Gemini 原生计数
- `API Key` 鉴权是可选的：`GEMINI_GATEWAY_API_KEY` 留空时匿名开放，设置后要求 `Authorization: Bearer <key>`

## 项目结构

```text
.
├── cli.py
├── docker-compose.yml
├── Dockerfile
├── .env.docker
├── .env.docker.example
├── requirements.txt
└── gemini_webapi
    ├── client.py
    ├── constants.py
    ├── exceptions.py
    ├── openai_server
    │   ├── adapter.py
    │   ├── app.py
    │   ├── client_manager.py
    │   ├── config.py
    │   ├── errors.py
    │   └── schemas.py
    ├── components
    ├── types
    └── utils
```

## 环境要求

- Python 3.12
- 一个可访问 Gemini 的 Google 账号
- 有效的 `cookies.json`，至少包含 `__Secure-1PSID`
- 如果你的账号需要，建议同时提供 `__Secure-1PSIDTS`

## `cookies.json` 支持格式

当前代码支持几种常见格式。

扁平对象：

```json
{
  "__Secure-1PSID": "xxx",
  "__Secure-1PSIDTS": "yyy"
}
```

嵌套对象：

```json
{
  "cookies": {
    "__Secure-1PSID": "xxx",
    "__Secure-1PSIDTS": "yyy"
  }
}
```

数组格式：

```json
[
  { "name": "__Secure-1PSID", "value": "xxx" },
  { "name": "__Secure-1PSIDTS", "value": "yyy" }
]
```

## Docker Compose 快速部署

这是当前最推荐的运行方式。

### 1. 准备文件

- 把 Gemini Cookie 放进 `./cookies.json`
- 查看 `.env.docker.example` 了解可配置项
- 确保 `.env.docker` 里是你希望容器使用的配置
- 确保存在 `./docker-data` 目录，用于持久化 Cookie 缓存和刷新数据
- `GEMINI_GATEWAY_API_KEY` 留空表示匿名访问；设置后就启用 Bearer Token 鉴权

### 2. 后台启动

```bash
docker compose up -d --build
```

这里一定要用 `-d`。这样容器会在后台运行，关闭终端后不会跟着停掉。

### 3. 查看状态

```bash
docker compose ps
docker logs -f gemini-gateway
```

### 4. 停止服务

```bash
docker compose down
```

### 5. 健康检查

```bash
curl http://127.0.0.1:9090/health
```

## Docker 部署说明

当前 `docker-compose.yml` 会：

- 把 `./cookies.json` 挂载到容器内 `/app/cookies/cookies.json`
- 把 `./docker-data` 挂载到容器内 `/app/docker-data`
- 把容器 `9090` 端口映射到宿主机 `9090`
- 使用 `restart: unless-stopped`

有一个很重要的当前实现细节：

- 镜像里的 Uvicorn 启动命令写死在 `Dockerfile`
- 目前固定监听 `0.0.0.0:9090`
- 所以虽然配置里有 `GEMINI_GATEWAY_HOST` 和 `GEMINI_GATEWAY_PORT`，但当前镜像启动命令仍然固定使用 `9090`

如果你只是想改宿主机暴露端口，可以只改映射，例如：

```yaml
ports:
  - "8080:9090"
```

如果你想改容器内应用监听端口，就需要同时修改容器启动命令。

## `.env.docker.example`

仓库新增了 `.env.docker.example`，用来作为 Docker 部署参考。

主要变量：

- `GEMINI_GATEWAY_COOKIE_PATH`: 容器内 Cookie 文件路径
- `GEMINI_GATEWAY_MODEL_DEFAULT`: 当客户端没传 `model` 时使用的默认模型
- `GEMINI_GATEWAY_LOG_LEVEL`: `INFO` 或 `DEBUG`
- `GEMINI_GATEWAY_REQUEST_TIMEOUT`: 单次请求超时时间，单位秒
- `GEMINI_COOKIE_PATH`: 容器内 Cookie 缓存目录
- `GEMINI_GATEWAY_API_KEY`: 留空表示匿名模式；设置密钥后启用 Bearer Token 鉴权

## 不用 Docker 的本地运行方式

安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

启动 OpenAI 兼容网关：

```bash
export GEMINI_GATEWAY_COOKIE_PATH=./cookies.json
export GEMINI_GATEWAY_MODEL_DEFAULT=gemini-3-flash
export GEMINI_GATEWAY_REQUEST_TIMEOUT=300
python -m uvicorn gemini_webapi.openai_server.app:app --host 0.0.0.0 --port 9090
```

## OpenAI 兼容接口示例

鉴权模式：

- 匿名模式：`GEMINI_GATEWAY_API_KEY` 不设置或留空，请求时不用带 `Authorization`
- 受保护模式：设置 `GEMINI_GATEWAY_API_KEY=your-secret`，请求时带 `Authorization: Bearer your-secret`

查看模型：

```bash
curl http://127.0.0.1:9090/v1/models
```

非流式请求：

```bash
curl http://127.0.0.1:9090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash",
    "messages": [
      { "role": "system", "content": "你是一个简洁助手。" },
      { "role": "user", "content": "用三句话解释什么是反向代理。" }
    ]
  }'
```

流式请求：

```bash
curl http://127.0.0.1:9090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -N \
  -d '{
    "model": "gemini-3-flash",
    "stream": true,
    "messages": [
      { "role": "user", "content": "写一个最小 FastAPI hello-world 示例。" }
    ]
  }'
```

带 API Key 的请求示例：

```bash
curl http://127.0.0.1:9090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret" \
  -d '{
    "model": "gemini-3-flash",
    "messages": [
      { "role": "user", "content": "Say hello." }
    ]
  }'
```

### 用 OpenAI Python SDK 接入

如果网关运行在匿名模式，而你的 SDK 又强制要求 `api_key` 字段，可以传任意非空占位值。
如果网关运行在受保护模式，就传真实配置的密钥。

```python
from openai import OpenAI

client = OpenAI(api_key="dummy", base_url="http://127.0.0.1:9090/v1")

resp = client.chat.completions.create(
    model="gemini-3-flash",
    messages=[
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Explain Docker Compose in plain language."},
    ],
)

print(resp.choices[0].message.content)
```

受保护模式示例：

```python
client = OpenAI(api_key="your-secret", base_url="http://127.0.0.1:9090/v1")
```

## CLI 用法

入口：

```bash
python cli.py --help
```

单轮提问：

```bash
python cli.py --cookies-json ./cookies.json ask "总结一下 Docker Compose 的作用"
```

非流式：

```bash
python cli.py --cookies-json ./cookies.json ask "给我一个 Nginx 反向代理示例" --no-stream
```

继续聊天：

```bash
python cli.py --cookies-json ./cookies.json reply c_xxx "继续上一个回答"
```

列出聊天：

```bash
python cli.py --cookies-json ./cookies.json list
```

读取聊天并输出到文件：

```bash
python cli.py --cookies-json ./cookies.json read c_xxx --output ./chat.txt
```

查看内置模型：

```bash
python cli.py models
```

账号诊断：

```bash
python cli.py --cookies-json ./cookies.json inspect
```

常用参数：

- `--cookies-json`
- `--proxy`
- `--account-index`
- `--model`
- `--verbose`
- `--request-timeout`
- `--skip-verify`
- `--no-persist`

## 兼容性说明

下面这些 OpenAI 风格字段当前会被解析，但不会真正影响 Gemini 生成逻辑：

- `temperature`
- `top_p`
- `max_tokens`
- `stop`
- `seed`
- `presence_penalty`
- `frequency_penalty`
- `tools`
- `tool_choice`
- `function_call`
- `functions`
- `response_format`
- `logprobs`
- `top_logprobs`
- `modalities`
- `audio`

所以它更适合接入“只需要基础 Chat Completions 兼容”的客户端，而不是深度依赖 OpenAI 高级特性的应用。

## 模型说明

仓库当前包含这些模型名：

- `gemini-3-flash`
- `gemini-3-pro`
- `gemini-3-flash-thinking`
- `gemini-3-pro-plus`
- `gemini-3-flash-plus`
- `gemini-3-flash-thinking-plus`
- `gemini-3-pro-advanced`
- `gemini-3-flash-advanced`
- `gemini-3-flash-thinking-advanced`

具体是否可用，仍然取决于你的账号权限和地区。最稳妥的检查方式：

- 请求 `GET /v1/models`
- 执行 `python cli.py --cookies-json ./cookies.json inspect`

## 常见问题

### 报错 `__Secure-1PSID is required`

你的 `cookies.json` 缺少核心 Cookie，或者文件格式不符合当前加载器支持的格式。

### 请求返回 429 或 503

常见原因：

- Cookie 失效
- 账号或地区受限
- 当前 IP 或网络环境受限
- Google 侧临时异常

建议先执行：

```bash
python cli.py --cookies-json ./cookies.json inspect
```

如果需要代理：

```bash
python cli.py --cookies-json ./cookies.json --proxy http://127.0.0.1:7890 inspect
```

### 关闭终端后容器停止

请使用：

```bash
docker compose up -d
```

如果你执行的是前台模式 `docker compose up`，容器生命周期会绑定当前终端会话。

### 为什么现在既能支持带 API Key，也能支持不带 API Key？

完全由 `GEMINI_GATEWAY_API_KEY` 控制：

- 不设置或留空：`/v1/models` 和 `/v1/chat/completions` 允许匿名访问
- 设置为某个值：这两个接口要求 `Authorization: Bearer <该值>`
- `/health` 在两种模式下都保持公开
