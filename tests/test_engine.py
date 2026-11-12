"""Çağrı motoru: önbellek, kayıt, doğrulama yeniden denemesi, geçici hatada geri çekilme."""
import asyncio
import json

import pytest

from scoring.config import ModelsConfig
from scoring.engine import CallEngine, Job, load_call_ids
from scoring.providers import LLMRequest, LLMResult, RetryableError, effective_params
from scoring.providers.base import Provider


def _models(**params):
    spec = {"provider": "mock", "model": "fake-1", "open_weights": True, "params": {"temperature": 0, **params}}
    return ModelsConfig(scorers=["a", "b"], aggregator="a", models={"a": spec, "b": spec},
                        retry={"max_validation_retries": 2, "max_api_retries": 3,
                               "backoff_initial_seconds": 0.001, "backoff_max_seconds": 0.002})


class FakeProvider(Provider):
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def complete(self, req):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(item, 10, 5, "fake-1-2026-01-01", 0.01)


def _validator(text):
    try:
        d = json.loads(text)
        return d, None
    except json.JSONDecodeError as e:
        return None, str(e)


def _engine(tmp_path, provider):
    eng = CallEngine(_models(), "run1", tmp_path / "cache.sqlite", tmp_path / "logs")
    eng._providers["a"] = provider
    eng._sems["a"] = asyncio.Semaphore(2)
    return eng


def _job():
    return Job(LLMRequest("a", "sys", [{"role": "user", "content": "puanla"}],
                          {"layer": 1, "variant": "anchored", "replicate": 1, "response_id": "R1", "item_id": "S1"}),
               _validator)


def test_validation_retry_and_logging(tmp_path):
    prov = FakeProvider(["not json", '{"ok": 1}'])
    eng = _engine(tmp_path, prov)
    [o] = asyncio.run(eng.run([_job()]))
    assert o.parsed == {"ok": 1} and len(o.call_ids) == 2 and o.call_id == o.call_ids[-1]
    lines = [json.loads(x) for x in (tmp_path / "logs/run1/calls.jsonl").read_text().splitlines()]
    assert [ln["attempt"] for ln in lines] == [0, 1]
    assert lines[0]["validation_error"] and lines[1]["validation_error"] is None
    for k in ("timestamp", "model_requested", "model_version_returned", "provider", "params", "template_name",
              "prompt_sha256", "prompt_text", "raw_response", "parsed_output", "input_tokens", "output_tokens",
              "latency_s", "cost_usd_est", "error"):
        assert k in lines[0]
    # Düzeltme isteği ikinci çağrının istemine eklenmiş olmalı
    assert "geçersizdi" in lines[1]["prompt_text"]
    assert o.call_id in load_call_ids(tmp_path / "logs")


def test_cache_prevents_second_call(tmp_path):
    prov = FakeProvider(['{"ok": 1}'])
    asyncio.run(_engine(tmp_path, prov).run([_job()]))
    prov2 = FakeProvider([])
    [o] = asyncio.run(_engine(tmp_path, prov2).run([_job()]))
    assert prov2.calls == 0 and o.parsed == {"ok": 1}
    # Farklı replikasyon önbelleği paylaşmaz
    j = _job(); j.request.metadata["replicate"] = 2
    prov3 = FakeProvider(['{"ok": 2}'])
    [o3] = asyncio.run(_engine(tmp_path, prov3).run([j]))
    assert prov3.calls == 1 and o3.parsed == {"ok": 2}


def test_retryable_error_backoff(tmp_path):
    prov = FakeProvider([RetryableError("429"), RetryableError("429"), '{"ok": 1}'])
    eng = _engine(tmp_path, prov)
    [o] = asyncio.run(eng.run([_job()]))
    assert o.parsed == {"ok": 1} and prov.calls == 3 and eng.stats["api_retries"] == 2


def test_permanent_error_recorded_not_raised(tmp_path):
    prov = FakeProvider([ValueError("400 bad request")])
    [o] = asyncio.run(_engine(tmp_path, prov).run([_job()]))
    assert o.parsed is None and "400" in o.error


def test_anthropic_never_sends_temperature():
    from scoring.config import ModelSpec
    spec = ModelSpec(provider="anthropic", model="claude-opus-5-5", params={"temperature": 0, "max_tokens": 10})
    p = effective_params(spec)
    assert str(p["temperature"]).startswith("unsupported")
    from scoring.providers.anthropic_provider import AnthropicProvider
    body = AnthropicProvider.__new__(AnthropicProvider)
    body.spec = spec
    params = body._params(LLMRequest("x", "s", [{"role": "user", "content": "u"}]))
    assert "temperature" not in params and params["system"] == "s"


def test_openai_body_has_temperature_and_json():
    from scoring.config import ModelSpec
    from scoring.providers.openai_provider import OpenAIProvider
    spec = ModelSpec(provider="openai", model="gpt-x", params={"temperature": 0, "seed": 1, "max_tokens": 10})
    p = OpenAIProvider.__new__(OpenAIProvider)
    p.spec = spec
    b = p._body(LLMRequest("x", "s", [{"role": "user", "content": "u"}]))
    assert b["temperature"] == 0 and b["seed"] == 1 and b["response_format"] == {"type": "json_object"}
    assert b["messages"][0] == {"role": "system", "content": "s"}
