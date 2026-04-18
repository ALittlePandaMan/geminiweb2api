# Gemini WebAPI Gateway

English | [简体中文](README_CN.md)

Gemini WebAPI Gateway is a private/self-hosted gateway that uses browser cookies to access Gemini and exposes:

- a local CLI for direct usage
- an OpenAI-compatible HTTP API for existing SDKs and tools

This repository currently focuses on practical deployment, especially Docker Compose deployment, rather than a polished public SDK surface.

## Features

- Cookie-based Gemini session bootstrap from `cookies.json`
- CLI commands for asking, continuing chats, listing chats, reading chats, and account inspection
- OpenAI-compatible endpoints:
  - `GET /health`
  - `GET /v1/models`
  - `POST /v1/chat/completions`
- Non-streaming and SSE streaming chat responses
- Image input support through OpenAI-style `image_url` parts
  - supports `data:image/...;base64,...`
  - supports `http(s)://...` image URLs
- Docker Compose deployment template
- Cookie cache persistence through a mounted data directory

## Current Scope And Limits

- Only `/v1/models` and `/v1/chat/completions` are implemented
- Image input is supported only through OpenAI-style `image_url` message parts
- Many OpenAI request fields are accepted for compatibility but ignored later
- `n` must be `1`
- Tool calling, function calling, structured output, audio, and multimodal input are not implemented
- OpenAI `messages` are flattened into a single text prompt before being sent to Gemini
- Direct OpenAI file-upload APIs are still not implemented
- `usage` token counts are local estimates, not Gemini-native token accounting
- API key auth is optional: leave `GEMINI_GATEWAY_API_KEY` empty for public access, or set it to require `Authorization: Bearer <key>`

## Project Layout

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

## Requirements

- Python 3.12
- A Google account that can access Gemini
- A valid `cookies.json` that includes at least `__Secure-1PSID`
- `__Secure-1PSIDTS` is strongly recommended when your account requires it

## Cookie File Formats

The code accepts several `cookies.json` layouts.

Flat object:

```json
{
  "__Secure-1PSID": "xxx",
  "__Secure-1PSIDTS": "yyy"
}
```

Nested object:

```json
{
  "cookies": {
    "__Secure-1PSID": "xxx",
    "__Secure-1PSIDTS": "yyy"
  }
}
```

Array form:

```json
[
  { "name": "__Secure-1PSID", "value": "xxx" },
  { "name": "__Secure-1PSIDTS", "value": "yyy" }
]
```

## Quick Start With Docker Compose

This is the recommended way to run the project.

### 1. Prepare files

- Put your Gemini cookies into `./cookies.json`
- Review `.env.docker.example`
- Make sure `.env.docker` contains the values you want the container to use
- Ensure `./docker-data` exists so refreshed cookie/cache data can persist
- Leave `GEMINI_GATEWAY_API_KEY` empty for anonymous access, or set it to enforce bearer-token auth

### 2. Start the gateway

```bash
docker compose up -d --build
```

This runs the container in detached mode, so closing the terminal does not stop it.

### 3. Check status

```bash
docker compose ps
docker logs -f gemini-gateway
```

### 4. Stop it

```bash
docker compose down
```

### 5. Health check

```bash
curl http://127.0.0.1:9090/health
```

## Docker Deployment Notes

The current compose setup:

- mounts `./cookies.json` to `/app/cookies/cookies.json`
- mounts `./docker-data` to `/app/docker-data`
- publishes container port `9090` to host port `9090`
- uses `restart: unless-stopped`

Important detail:

- The bundled image starts Uvicorn with a fixed command in `Dockerfile`
- That command currently binds to `0.0.0.0:9090`
- `GEMINI_GATEWAY_HOST` and `GEMINI_GATEWAY_PORT` exist in config, but the shipped container command still hardcodes `9090`

If you only want a different host-side port, change the compose mapping, for example:

```yaml
ports:
  - "8080:9090"
```

If you want the app inside the container to listen on another port, you need to change the container command as well.

## `.env.docker.example`

An example file is included at `.env.docker.example` as a deployment reference.

Key variables:

- `GEMINI_GATEWAY_COOKIE_PATH`: path to the mounted cookie file inside the container
- `GEMINI_GATEWAY_MODEL_DEFAULT`: default model when the client does not send `model`
- `GEMINI_GATEWAY_LOG_LEVEL`: `INFO` or `DEBUG`
- `GEMINI_GATEWAY_REQUEST_TIMEOUT`: per-request timeout in seconds
- `GEMINI_COOKIE_PATH`: cookie cache directory inside the container
- `GEMINI_GATEWAY_API_KEY`: leave empty for anonymous mode, or set a secret to require bearer-token auth

## Local Run Without Docker

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Start the OpenAI-compatible gateway:

```bash
export GEMINI_GATEWAY_COOKIE_PATH=./cookies.json
export GEMINI_GATEWAY_MODEL_DEFAULT=gemini-3-flash
export GEMINI_GATEWAY_REQUEST_TIMEOUT=300
python -m uvicorn gemini_webapi.openai_server.app:app --host 0.0.0.0 --port 9090
```

## OpenAI-Compatible API Usage

Auth modes:

- Anonymous mode: leave `GEMINI_GATEWAY_API_KEY` unset or empty, then call the API without `Authorization`
- Protected mode: set `GEMINI_GATEWAY_API_KEY=your-secret`, then include `Authorization: Bearer your-secret`

List models:

```bash
curl http://127.0.0.1:9090/v1/models
```

Non-streaming chat:

```bash
curl http://127.0.0.1:9090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash",
    "messages": [
      { "role": "system", "content": "You are a concise assistant." },
      { "role": "user", "content": "Explain reverse proxy in three sentences." }
    ]
  }'
```

Streaming chat:

```bash
curl http://127.0.0.1:9090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -N \
  -d '{
    "model": "gemini-3-flash",
    "stream": true,
    "messages": [
      { "role": "user", "content": "Write a minimal FastAPI hello-world example." }
    ]
  }'
```

Protected request example:

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

### Using The OpenAI Python SDK

If the gateway runs in anonymous mode and your SDK still requires an API key field, pass any non-empty placeholder value.
If the gateway runs in protected mode, pass the real configured key.

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

In protected mode:

```python
client = OpenAI(api_key="your-secret", base_url="http://127.0.0.1:9090/v1")
```

## CLI Usage

Entry point:

```bash
python cli.py --help
```

Ask once:

```bash
python cli.py --cookies-json ./cookies.json ask "Summarize what Docker Compose does"
```

Ask once without streaming:

```bash
python cli.py --cookies-json ./cookies.json ask "Give me an Nginx reverse proxy example" --no-stream
```

Continue a chat:

```bash
python cli.py --cookies-json ./cookies.json reply c_xxx "Continue the previous answer"
```

List chats:

```bash
python cli.py --cookies-json ./cookies.json list
```

Read a chat into a file:

```bash
python cli.py --cookies-json ./cookies.json read c_xxx --output ./chat.txt
```

List built-in models:

```bash
python cli.py models
```

Inspect account status:

```bash
python cli.py --cookies-json ./cookies.json inspect
```

Useful flags:

- `--cookies-json`
- `--proxy`
- `--account-index`
- `--model`
- `--verbose`
- `--request-timeout`
- `--skip-verify`
- `--no-persist`

## Compatibility Notes

The following OpenAI-style fields are currently parsed but not meaningfully applied to Gemini generation:

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

This gateway is best suited for clients that only need baseline Chat Completions compatibility.

## Models

The repository currently contains these model names:

- `gemini-3-flash`
- `gemini-3-pro`
- `gemini-3-flash-thinking`
- `gemini-3-pro-plus`
- `gemini-3-flash-plus`
- `gemini-3-flash-thinking-plus`
- `gemini-3-pro-advanced`
- `gemini-3-flash-advanced`
- `gemini-3-flash-thinking-advanced`

Actual availability still depends on your account and region. The safest checks are:

- `GET /v1/models`
- `python cli.py --cookies-json ./cookies.json inspect`

## Troubleshooting

### `__Secure-1PSID is required`

Your `cookies.json` is missing the core Gemini cookie, or the file format is not supported by the current loader.

### 429 or 503 errors

Common causes:

- expired cookies
- account or region restrictions
- IP/network restrictions
- temporary Google-side availability issues

Useful check:

```bash
python cli.py --cookies-json ./cookies.json inspect
```

With a proxy:

```bash
python cli.py --cookies-json ./cookies.json --proxy http://127.0.0.1:7890 inspect
```

### Container stops when the terminal closes

Use detached mode:

```bash
docker compose up -d
```

If you run `docker compose up` in the foreground, the lifecycle stays attached to the current terminal session.

### Why do both API key and no-API-key calls work?

This is controlled entirely by `GEMINI_GATEWAY_API_KEY`:

- unset or empty: `/v1/models` and `/v1/chat/completions` are public
- set to a value: those endpoints require `Authorization: Bearer <that-value>`
- `/health` remains public in both modes
