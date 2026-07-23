"""Live LLM backend for any OpenAI-compatible endpoint (incl. 火山方舟/Ark).

Zero heavy deps — the HTTP call is done with ``urllib`` from the stdlib, staying
faithful to the project's "stdlib + requests only" rule. Credentials are read
**only from environment variables** (optionally loaded from a local ``.env``);
nothing is ever hard-coded.

Works with any provider that speaks the OpenAI ``/chat/completions`` shape:

    OpenAI        base_url=https://api.openai.com/v1              model=gpt-4o-mini
    火山方舟/Ark   base_url=https://ark.cn-beijing.volces.com/api/v3 model=ep-xxxxxxxx / doubao-...
    DeepSeek      base_url=https://api.deepseek.com/v1            model=deepseek-chat
    通义千问       base_url=https://dashscope.aliyuncs.com/compatible-mode/v1  model=qwen-plus
    Moonshot      base_url=https://api.moonshot.cn/v1            model=moonshot-v1-8k

Env vars (prefix ``STOCK_LLM_``):

    STOCK_LLM_BASE_URL   required, e.g. https://ark.cn-beijing.volces.com/api/v3
    STOCK_LLM_API_KEY    required
    STOCK_LLM_MODEL      required, e.g. ep-xxxx / gpt-4o-mini / deepseek-chat
    STOCK_LLM_TIMEOUT    optional, seconds (default 60)
    STOCK_LLM_JSON_MODE  optional: auto (default) | on | off
                         auto = send {"type":"json_object"} and retry without it
                         if the endpoint rejects it (some models don't support it)

Build one with :func:`build_live_llm` and hand it to ``run_pipeline`` /
``run_deep_research`` exactly like the ``FakeLLM``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .llm import OpenAICompatibleLLM


def load_dotenv(path: str = ".env") -> None:
    """Load ``KEY=VALUE`` lines from a local .env into ``os.environ``.

    Best-effort and dependency-free. Existing env vars win (so an explicitly
    exported value is never clobbered by the file). Lines starting with ``#``
    and blank lines are ignored; surrounding quotes are stripped.
    """
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _normalize_base_url(base_url: str) -> str:
    """Return the full ``.../chat/completions`` URL from a base endpoint."""
    url = base_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return url + "/chat/completions"


class LiveLLMError(RuntimeError):
    """Raised when the endpoint is misconfigured or the request fails."""


def build_live_llm(
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    default_model: Optional[str] = None,
    timeout: Optional[float] = None,
    json_mode: Optional[str] = None,
) -> OpenAICompatibleLLM:
    """Build an ``OpenAICompatibleLLM`` wired to a real endpoint.

    Missing args fall back to the ``STOCK_LLM_*`` env vars. Raises
    ``LiveLLMError`` early with a clear message if base_url / api_key / model
    are absent, so we never fire a request that is doomed to 401.
    """
    base_url = base_url or os.environ.get("STOCK_LLM_BASE_URL", "")
    api_key = api_key or os.environ.get("STOCK_LLM_API_KEY", "")
    default_model = default_model or os.environ.get("STOCK_LLM_MODEL", "")
    timeout = timeout if timeout is not None else float(os.environ.get("STOCK_LLM_TIMEOUT", "60"))
    json_mode = (json_mode or os.environ.get("STOCK_LLM_JSON_MODE", "auto")).lower()

    missing = [
        name
        for name, val in (
            ("STOCK_LLM_BASE_URL", base_url),
            ("STOCK_LLM_API_KEY", api_key),
            ("STOCK_LLM_MODEL", default_model),
        )
        if not val
    ]
    if missing:
        raise LiveLLMError(
            "Missing required config: " + ", ".join(missing) + ". "
            "Set them as environment variables or in a local .env "
            "(see .env.example)."
        )

    endpoint = _normalize_base_url(base_url)

    def _post(payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            raise LiveLLMError(f"HTTP {e.code} from {endpoint}: {body}") from e
        except urllib.error.URLError as e:
            raise LiveLLMError(f"Cannot reach {endpoint}: {e.reason}") from e

    def call_fn(*, messages, model, temperature, response_format=None):
        payload = {
            "model": model or default_model,
            "messages": messages,
            "temperature": temperature,
        }
        want_json = response_format == "json" and json_mode != "off"
        if want_json:
            payload["response_format"] = {"type": "json_object"}
        try:
            body = _post(payload)
        except LiveLLMError:
            # Some models reject response_format; in "auto" mode retry without it.
            if want_json and json_mode == "auto":
                payload.pop("response_format", None)
                body = _post(payload)
            else:
                raise
        try:
            return body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LiveLLMError(f"Unexpected response shape: {json.dumps(body)[:400]}") from e

    return OpenAICompatibleLLM(call_fn=call_fn, default_model=default_model)
