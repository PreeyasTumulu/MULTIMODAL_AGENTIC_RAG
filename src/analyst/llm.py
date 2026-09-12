"""One chat client for every LLM provider in ADR-002.

Groq and OpenRouter speak the OpenAI chat-completions protocol, so swapping
between them is a base URL, a key and a model name - configuration, not code.

Ollama is the exception, and the reason is measured rather than stylistic. Its
OpenAI-compatible endpoint cannot set the context window, and on this machine it
SILENTLY cut an 11,021-token prompt to 2,050 tokens: no error, the model simply
answered `{}`. A 10-chunk evidence prompt would lose most of its evidence the
same way. The native `/api/chat` accepts `num_ctx`, and the identical prompt
then arrives whole. So Ollama gets its own wire format and nothing else changes.

Every call is JSON mode at temperature 0, and cached on disk. The cache is not an
optimisation: the free tier is a daily token budget, and re-scoring an unchanged
evaluation run must spend none of it.
"""

import base64
import hashlib
import json
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from analyst.config import ROOT, Settings

OPENAI_COMPATIBLE = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
CACHE = ROOT / "data" / "llm_cache.sqlite"  # data/ is git-ignored
NUM_CTX = 16_384  # ~30 evidence chunks; Ollama's default truncated silently


@dataclass(frozen=True)
class Reply:
    data: dict[str, object]
    prompt_tokens: int
    completion_tokens: int
    ms: float  # of the original call, even when served from cache
    cached: bool


def parse_json(text: str) -> dict[str, object]:
    """The outermost {...} of a reply, or {} when there is none.

    JSON mode is a request, not a guarantee: small local models still wrap the
    object in prose. An unusable reply becomes an empty one, which every caller
    already treats as "no answer" - so the agent refuses instead of crashing.
    """
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _retryable(e: BaseException) -> bool:
    """Rate limits and server hiccups are worth waiting out; a 400 is a bug."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(e, httpx.TransportError)


class LLM:
    def __init__(
        self,
        settings: Settings,
        provider: str | None = None,
        model: str | None = None,
        cache: Path | None = CACHE,
        http: httpx.Client | None = None,
    ) -> None:
        self.provider = provider or settings.llm_provider
        self.model = model or settings.llm_model
        self.headers: dict[str, str] = {}
        if self.provider == "ollama":
            self.url = f"{settings.ollama_base_url}/api/chat"
        elif self.provider in OPENAI_COMPATIBLE:
            key = getattr(settings, f"{self.provider}_api_key")
            # An empty `GROQ_API_KEY=` line parses as "", not None - and would
            # otherwise surface as a baffling 401 on the first call.
            if not key or not key.get_secret_value():
                raise ValueError(f"{self.provider.upper()}_API_KEY is empty in .env")
            self.url = f"{OPENAI_COMPATIBLE[self.provider]}/chat/completions"
            self.headers["Authorization"] = f"Bearer {key.get_secret_value()}"
        else:
            raise ValueError(f"unknown LLM provider {self.provider!r}")
        self.http = http or httpx.Client(timeout=300)
        self.db: sqlite3.Connection | None = None
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(cache, check_same_thread=False)
            self.db.execute("CREATE TABLE IF NOT EXISTS replies (key TEXT PRIMARY KEY, reply TEXT)")

    @property
    def name(self) -> str:
        return f"{self.provider}/{self.model}"

    def complete(self, system: str, user: str, images: Sequence[bytes] = ()) -> Reply:
        """One JSON-mode call at temperature 0, served from cache when seen before.

        `images` (PNG bytes) go with the user message, for a vision model. They
        join the cache key by digest, and only when present, so every text-only
        reply cached before images existed is still found.
        """
        key_parts: list[object] = [self.name, [{"role": "system", "content": system},
                                               {"role": "user", "content": user}]]
        if images:
            key_parts.append([hashlib.sha256(i).hexdigest() for i in images])
        key = hashlib.sha256(json.dumps(key_parts).encode()).hexdigest()
        if self.db and (
            row := self.db.execute("SELECT reply FROM replies WHERE key = ?", (key,)).fetchone()
        ):
            text, pt, ct, ms = json.loads(row[0])
            return Reply(parse_json(text), pt, ct, ms, cached=True)
        t0 = time.perf_counter()
        text, pt, ct = self._post(system, user, [base64.b64encode(i).decode() for i in images])
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if self.db:
            self.db.execute("INSERT OR REPLACE INTO replies VALUES (?, ?)",
                            (key, json.dumps([text, pt, ct, ms])))
            self.db.commit()
        return Reply(parse_json(text), pt, ct, ms, cached=False)

    @retry(retry=retry_if_exception(_retryable), wait=wait_exponential(min=2, max=60),
           stop=stop_after_attempt(6), reraise=True)
    def _post(self, system: str, user: str, pics: list[str]) -> tuple[str, int, int]:
        body: dict[str, object]
        if self.provider == "ollama":
            # Native format: images ride on the message as bare base64.
            msg: dict[str, object] = {"role": "user", "content": user}
            if pics:
                msg["images"] = pics
            body = {"model": self.model, "stream": False, "format": "json",
                    "messages": [{"role": "system", "content": system}, msg],
                    "options": {"temperature": 0, "num_ctx": NUM_CTX}}
        else:
            # OpenAI format: images are content parts, as data URLs.
            content: object = [{"type": "text", "text": user}, *(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{p}"}}
                for p in pics)] if pics else user
            body = {"model": self.model, "temperature": 0,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": content}],
                    "response_format": {"type": "json_object"}}
        r = self.http.post(self.url, json=body, headers=self.headers)
        r.raise_for_status()
        d = r.json()
        if self.provider == "ollama":
            return d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)
        usage = d.get("usage") or {}
        return (d["choices"][0]["message"]["content"],
                usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
