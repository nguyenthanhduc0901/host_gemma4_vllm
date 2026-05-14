# vLLM API Usage Guide (Gemma 4 E4B)

## Base URL
VM_EXTERNAL_IP = 34.87.147.181

Replace `<VM_EXTERNAL_IP>` with your VM public IP.

- From **outside** the VM:
  - `http://<VM_EXTERNAL_IP>:8000`

All examples below assume:

- Model name: `gemma-4-e4b-it`
- Header: `Content-Type: application/json`

## Quick smoke tests

### Health

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/health
```

### List served models

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/models
```

### Chat completion (non-streaming)

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Chào bạn! Trả lời 1 câu ngắn: bạn là ai?"}],
  "max_tokens": 64,
  "temperature": 0.2
}
JSON
```

## Streaming support (important)

### How to test streaming with curl

Use `-N` to disable buffering so you can see tokens/events as they arrive:

```bash
curl -sS -N http://<VM_EXTERNAL_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Đếm từ 1 đến 5, mỗi số một dòng."}],
  "max_tokens": 64,
  "temperature": 0,
  "stream": true
}
JSON
```

## Endpoint reference (with test commands)

Below is the list of endpoints observed from the server OpenAPI spec.

---

## 1) Health / metadata / metrics

### `GET /health`

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/health
```

### `GET /ping` (and `POST /ping`)

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/ping
```

### `GET /version`

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/version
```

### `GET /metrics` (Prometheus)

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/metrics | head
```

### `GET /load` (server load metric)

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/load
```

---

## 2) OpenAI-compatible API

### `GET /v1/models`

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/models
```

### `POST /v1/chat/completions`

Non-streaming:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Trả lời đúng 1 từ: OK"}],
  "max_tokens": 8,
  "temperature": 0
}
JSON
```

Streaming:

```bash
curl -sS -N http://<VM_EXTERNAL_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Viết 10 từ tiếng Việt."}],
  "max_tokens": 64,
  "temperature": 0.2,
  "stream": true
}
JSON
```

### `POST /v1/chat/completions/batch`

Send multiple conversations in one request.

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/chat/completions/batch \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [
    [{"role":"user","content":"Trả lời 1 từ: A"}],
    [{"role":"user","content":"Trả lời 1 từ: B"}]
  ],
  "max_tokens": 4,
  "temperature": 0
}
JSON
```

### `POST /v1/chat/completions/render`

Renders the chat request into the low-level tokenization/sampling representation.

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/chat/completions/render \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [
    {"role": "system", "content": "Bạn là trợ lý."},
    {"role": "user", "content": "Xin chào"}
  ]
}
JSON
```

## 3) OpenAI Responses API

### `POST /v1/responses`

Non-streaming:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "input": "Trả lời đúng 1 từ: OK",
  "max_output_tokens": 16
}
JSON
```

Streaming (event stream):

```bash
curl -sS -N http://<VM_EXTERNAL_IP>:8000/v1/responses \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "input": "Viết 5 từ, cách nhau bởi dấu phẩy.",
  "stream": true,
  "max_output_tokens": 32
}
JSON
```

### `GET /v1/responses/{response_id}`

This works only when the vLLM **Responses store** feature is enabled.

- In this repo, it is enabled by setting `VLLM_ENABLE_RESPONSES_API_STORE=1` in the startup script.
- If store is disabled, `GET /v1/responses/{id}` will typically return `404`.

Retrieve a stored response:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses/resp_XXXX
```

End-to-end test (create with `store:true`, then GET by id):

```bash
resp=$(curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses \
  -H "Content-Type: application/json" \
  --data-binary '{"model":"gemma-4-e4b-it","input":"Trả lời 1 từ: OK","max_output_tokens":16,"store":true}')

rid=$(echo "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "RID=$rid"

curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses/$rid
```

### `POST /v1/responses/{response_id}/cancel`

Cancel a background response:

```bash
curl -sS -X POST http://<VM_EXTERNAL_IP>:8000/v1/responses/resp_XXXX/cancel
```

End-to-end cancel test (create `background:true`, then cancel):

```bash
resp=$(curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "input": "Viết một bài rất dài (>= 500 từ) về cách triển khai LLM trên GPU, chia nhiều mục.",
  "background": true,
  "max_output_tokens": 1024
}
JSON
)

rid=$(echo "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "RID=$rid"

curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses/$rid
curl -sS -X POST http://<VM_EXTERNAL_IP>:8000/v1/responses/$rid/cancel
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/responses/$rid
```

---

## 4) Anthropic-compatible API

### `POST /v1/messages`

Non-streaming:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Trả lời đúng 1 từ: OK"}],
  "max_tokens": 16,
  "stream": false
}
JSON
```

Streaming:

```bash
curl -sS -N http://<VM_EXTERNAL_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Nói 'OK' 5 lần, cách nhau bởi dấu phẩy."}],
  "max_tokens": 32,
  "stream": true
}
JSON
```

### `POST /v1/messages/count_tokens`

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/v1/messages/count_tokens \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Xin chào"}]
}
JSON
```

---

## 5) Token utilities

### `POST /tokenize`

Completion-style tokenization:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/tokenize \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "prompt": "Xin chào"
}
JSON
```

Chat-style tokenization:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/tokenize \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Xin chào"}],
  "add_generation_prompt": true
}
JSON
```

### `POST /detokenize`

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/detokenize \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "tokens": [72610, 36355]
}
JSON
```

---

## 6) Low-level generation

### `POST /inference/v1/generate`

This API uses `token_ids` instead of chat messages.

Example (using token IDs you got from `/tokenize`):

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/inference/v1/generate \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "token_ids": [72610, 36355],
  "sampling_params": {
    "max_tokens": 16,
    "temperature": 0
  }
}
JSON
```

Streaming is also supported via `"stream": true`:

```bash
curl -sS -N http://<VM_EXTERNAL_IP>:8000/inference/v1/generate \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "token_ids": [72610, 36355],
  "sampling_params": {"max_tokens": 32, "temperature": 0},
  "stream": true
}
JSON
```

---

## 7) Generative scoring

### `POST /generative_scoring`

Use this to score multiple candidate labels/items for the same query.

Working example:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/generative_scoring \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "query": "Hôm nay trời",
  "items": ["nắng", "mưa"],
  "label_token_ids": [236749, 236757]
}
JSON
```

Tip: `label_token_ids` should usually be the first token-id of each label (you can get it by calling `/tokenize` for each label string).

---

## 8) Elastic scaling (usually not needed)

### `POST /is_scaling_elastic_ep`

```bash
curl -sS -X POST http://<VM_EXTERNAL_IP>:8000/is_scaling_elastic_ep
```

### `POST /scale_elastic_ep`

```bash
curl -sS -X POST http://<VM_EXTERNAL_IP>:8000/scale_elastic_ep \
  -H "Content-Type: application/json" \
  --data-binary '{"new_data_parallel_size": 1}'
```

---

## 9) Compatibility alias

### `POST /invocations`

This endpoint accepts either an OpenAI Chat Completions payload or an OpenAI Completions payload.

Chat-style example:

```bash
curl -sS http://<VM_EXTERNAL_IP>:8000/invocations \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "model": "gemma-4-e4b-it",
  "messages": [{"role": "user", "content": "Trả lời 1 từ: OK"}],
  "max_tokens": 8,
  "temperature": 0
}
JSON
```

---

## Notes

- If a request returns `{"detail":"There was an error parsing the body"}`, it is usually a client-side quoting/JSON issue.
  Prefer the heredoc form (`--data-binary @- <<'JSON' ... JSON`) shown above.
- Some endpoints exist in OpenAPI but may not be fully functional depending on server configuration.
