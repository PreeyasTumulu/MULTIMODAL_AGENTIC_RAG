"""The LLM client against a fake HTTP transport - no network, no key, no quota."""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from analyst.config import Settings
from analyst.llm import LLM, NUM_CTX, parse_json

OPENAI_REPLY = {"choices": [{"message": {"content": '{"intent": "growth"}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3}}
OLLAMA_REPLY = {"message": {"content": 'Sure! {"intent": "price"}'},
                "prompt_eval_count": 9, "eval_count": 2}


def fake(reply: Mapping[str, object], seen: list[httpx.Request]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=reply)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_parse_json_survives_prose_and_garbage() -> None:
    assert parse_json('Here you go: {"a": 1} hope that helps') == {"a": 1}
    assert parse_json("no object here") == {}
    assert parse_json("[1, 2]") == {}


def test_groq_speaks_openai_json_mode_with_its_key() -> None:
    seen: list[httpx.Request] = []
    llm = LLM(Settings(groq_api_key=SecretStr("gsk_test")), "groq", "openai/gpt-oss-120b",
              cache=None, http=fake(OPENAI_REPLY, seen))
    r = llm.complete("sys", "user")
    body = json.loads(seen[0].content)
    assert (r.data, r.prompt_tokens, r.completion_tokens) == ({"intent": "growth"}, 12, 3)
    assert seen[0].url.path == "/openai/v1/chat/completions"
    assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
    assert seen[0].headers["Authorization"] == "Bearer gsk_test"


def test_ollama_uses_its_native_api_so_the_context_window_is_set() -> None:
    """Regression for a measured failure: the OpenAI-compatible endpoint cut an
    11,021-token prompt to 2,050 tokens without raising anything."""
    seen: list[httpx.Request] = []
    llm = LLM(Settings(), "ollama", "llama3.2", cache=None, http=fake(OLLAMA_REPLY, seen))
    r = llm.complete("sys", "user")
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/api/chat"
    assert body["options"]["num_ctx"] == NUM_CTX and body["format"] == "json"
    assert r.data == {"intent": "price"}


def test_a_repeated_call_is_served_from_cache(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    llm = LLM(Settings(), "ollama", "llama3.2", cache=tmp_path / "c.sqlite",
              http=fake(OLLAMA_REPLY, seen))
    first, second = llm.complete("s", "u"), llm.complete("s", "u")
    assert len(seen) == 1 and not first.cached and second.cached and second.data == first.data


def test_an_empty_key_fails_loudly_instead_of_as_a_401() -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        LLM(Settings(groq_api_key=SecretStr("")), "groq", "m", cache=None)


def test_images_ride_in_each_providers_own_format() -> None:
    seen: list[httpx.Request] = []
    LLM(Settings(), "ollama", "gemma3:4b", cache=None,
        http=fake(OLLAMA_REPLY, seen)).complete("s", "u", images=[b"png"])
    LLM(Settings(groq_api_key=SecretStr("k")), "groq", "v", cache=None,
        http=fake(OPENAI_REPLY, seen)).complete("s", "u", images=[b"png"])
    ollama, openai = (json.loads(r.content)["messages"][1] for r in seen)
    assert ollama["images"] == ["cG5n"]  # base64 of b"png"
    assert openai["content"][1]["image_url"]["url"] == "data:image/png;base64,cG5n"


def test_image_support_kept_the_cache_key_of_text_only_calls(tmp_path: Path) -> None:
    """Every reply cached before images existed must still be found."""
    llm = LLM(Settings(), "ollama", "m", cache=tmp_path / "c.sqlite", http=fake(OLLAMA_REPLY, []))
    llm.complete("s", "u")
    old = hashlib.sha256(json.dumps(["ollama/m", [{"role": "system", "content": "s"},
                                                  {"role": "user", "content": "u"}]]).encode())
    assert llm.db and llm.db.execute("SELECT 1 FROM replies WHERE key = ?",
                                     (old.hexdigest(),)).fetchone()
