"""
LLM client — OpenAI-compatible chat completions with streaming.

Default endpoint is the local Hermes proxy (`hermes proxy`), which exposes an
OpenAI-compatible API backed by your Nous/OAuth login — no API key needed.
Override via env vars:
    VORTEX_LLM_BASE_URL   e.g. https://api.openai.com/v1  (default http://localhost:8777/v1)
    VORTEX_LLM_API_KEY    (default "local" — hermes proxy accepts any)
    VORTEX_LLM_MODEL      model name (default "" — let the proxy decide)

Stdlib only (urllib) — no extra dependencies.
"""

import json
import urllib.error
import urllib.request

from ..vortex.settings import get_setting

BASE_URL = get_setting("llm_base_url").rstrip("/")
API_KEY = get_setting("llm_api_key")
MODEL = get_setting("llm_model")
TIMEOUT = 120


class LLMError(Exception):
    pass


def _post_json(path: str, payload: dict, timeout: int = TIMEOUT):
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "vortex-agent/1.0",  # proxy rejects default Python-urllib UA
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"LLM HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LLMError(
            f"Cannot reach LLM at {BASE_URL} ({e.reason}). "
            "Start the local proxy with `hermes proxy`, or set VORTEX_LLM_BASE_URL."
        ) from e


def chat_stream(messages, tools=None, model=None, temperature=0.7):
    """Stream chat completion deltas. Yields str chunks.

    messages: list of {"role": ..., "content": ...}
    tools:    optional list of OpenAI tool schemas
    """
    payload = {
        "model": model or MODEL,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    body = _post_json("/chat/completions", payload)
    # Streaming responses are SSE: lines of `data: {...}`, ending with `data: [DONE]`
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        finish = choices[0].get("finish_reason")
        if delta.get("content"):
            yield delta["content"]
        if delta.get("tool_calls"):
            yield json.dumps({"tool_calls": delta["tool_calls"]})


def chat_once(messages, tools=None, model=None, temperature=0.7):
    """Non-streaming completion. Returns full JSON object (may include tool_calls)."""
    payload = {
        "model": model or MODEL,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    body = _post_json("/chat/completions", payload)
    return json.loads(body)


def is_available():
    """Quick reachability check (returns bool)."""
    try:
        url = f"{BASE_URL}/models"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {API_KEY}", "User-Agent": "vortex-agent/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False
