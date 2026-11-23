# Optional Ollama recipe fallback (GitHub Issue #6)

Recipe generation has a cloud-first sequence:

1. Gemini `gemini-2.5-flash` (with retries on rate limiting)
2. Gemini `gemini-2.5-flash-lite` (with retries)
3. Ollama, **only when configured** and the cloud recipe agent fails or returns an invalid recipe
4. HTTP 502 with a truthful retry message when every configured provider fails

Cached recipes do not call the providers. Media/image retrieval remains
independent, and recipe output is checked against the existing recipe schema
and dietary incompatibility rules before caching.

## Render configuration (optional)

Set these **backend-only** environment variables:

| Variable | Value |
| --- | --- |
| `OLLAMA_BASE_URL` | HTTPS base URL of your reachable Ollama server, without a trailing `/api/generate` path |
| `OLLAMA_MODEL` | An installed model supporting structured JSON, e.g. `qwen2.5:7b` |
| `OLLAMA_TIMEOUT_SECONDS` | Optional fallback request timeout; default 20 seconds, allowed 2–30 seconds |

Both URL and model are required. If either is unset, the fallback is **disabled**
and Gemini continues to work as before. The API does not expose an Ollama URL
to users, and it never returns a fabricated recipe after a provider outage.

**Important hosting detail:** Ollama is a separate server process. Render's
`localhost` refers to the Render container; it cannot reach Ollama running on
your laptop or another computer at `localhost:11434`. Point Render to an
actually reachable instance over a trusted network or deploy Ollama alongside
the application. Do not expose an unauthenticated Ollama API to the public
internet; use network isolation and a trusted HTTPS reverse proxy.

Ollama `/api/generate` is called using non-streaming JSON output with an
asynchronous HTTP client and a bounded timeout. The fallback logs only the
provider and exception type, never prompt text or credentials. Only validated
recipes are cached. When the fallback is unavailable or invalid, the user
receives HTTP 502 and can retry rather than receiving placeholder cooking steps.

## Tests

Run the standard backend suite:

```bash
cd backend
python -m unittest discover -s tests -v
```

The fallback tests mock network/provider responses, so neither a Gemini key
nor an Ollama server is required for CI.
