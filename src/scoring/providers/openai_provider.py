"""OpenAI ve OpenAI uyumlu yerel uç noktalar (Ollama, vLLM)."""
from __future__ import annotations

import asyncio
import io
import json
import os
import time

from .base import LLMRequest, LLMResult, Provider, RetryableError


def _openai_errors():
    import openai
    return (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)


class OpenAIProvider(Provider):
    name = "openai"
    supports_batch = True

    def __init__(self, spec):
        super().__init__(spec)
        from openai import AsyncOpenAI
        self.client = self._make_client(AsyncOpenAI)

    def _make_client(self, cls):
        return cls(api_key=os.environ.get("OPENAI_API_KEY"), max_retries=0)

    def _body(self, req: LLMRequest) -> dict:
        p = self.spec.params
        messages = [{"role": "system", "content": req.system}, *req.messages]
        if p.get("system_in_user"):
            # Sistem rolünü desteklemeyen sohbet şablonları için (ör. bazı Gemma sürümleri)
            first = dict(req.messages[0])
            first["content"] = f"{req.system}\n\n{first['content']}"
            messages = [first, *req.messages[1:]]
        body = {"model": self.spec.model, "messages": messages, "max_tokens": p.get("max_tokens", 2000)}
        if p.get("json_schema") and req.metadata.get("json_schema"):
            # Kısıtlı çözümleme: sunucu çıktıyı şemaya uyan JSON ile sınırlar (llama.cpp, vLLM, Ollama ≥0.5)
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "puanlama", "schema": req.metadata["json_schema"],
                                                       "strict": True}}
        elif p.get("json_mode", True):
            body["response_format"] = {"type": "json_object"}
        if "temperature" in p:
            body["temperature"] = p["temperature"]
        if "seed" in p:
            body["seed"] = p["seed"]
        if p.get("extra_body"):
            # Sunucuya özgü alanlar; ör. vLLM/Qwen3: {"chat_template_kwargs": {"enable_thinking": false}}
            body["extra_body"] = p["extra_body"]
        return body

    @staticmethod
    def _parse(resp: dict, latency: float) -> LLMResult:
        choice = resp["choices"][0]
        usage = resp.get("usage") or {}
        return LLMResult(text=choice["message"].get("content") or "", input_tokens=usage.get("prompt_tokens"),
                         output_tokens=usage.get("completion_tokens"), model_version_returned=resp.get("model"),
                         latency_s=latency,
                         raw={"id": resp.get("id"), "finish_reason": choice.get("finish_reason"),
                              "system_fingerprint": resp.get("system_fingerprint")})

    async def complete(self, req: LLMRequest) -> LLMResult:
        t0 = time.perf_counter()
        try:
            resp = await self.client.chat.completions.create(**self._body(req))
        except _openai_errors() as e:
            raise RetryableError(f"{type(e).__name__}: {e}") from e
        return self._parse(resp.model_dump(), time.perf_counter() - t0)

    async def complete_batch(self, reqs: list[LLMRequest], poll_seconds: float = 30) -> list[LLMResult]:
        lines = [json.dumps({"custom_id": f"r{i}", "method": "POST", "url": "/v1/chat/completions",
                             "body": self._body(r)}, ensure_ascii=False) for i, r in enumerate(reqs)]
        f = await self.client.files.create(file=("batch.jsonl", io.BytesIO("\n".join(lines).encode())),
                                           purpose="batch")
        batch = await self.client.batches.create(input_file_id=f.id, endpoint="/v1/chat/completions",
                                                 completion_window="24h")
        t0 = time.perf_counter()
        while batch.status not in ("completed", "failed", "expired", "cancelled"):
            await asyncio.sleep(poll_seconds)
            batch = await self.client.batches.retrieve(batch.id)
        latency = time.perf_counter() - t0
        results: dict[str, LLMResult] = {}
        if batch.output_file_id:
            content = (await self.client.files.content(batch.output_file_id)).text
            for ln in content.splitlines():
                o = json.loads(ln)
                if o.get("response") and o["response"].get("status_code") == 200:
                    r = self._parse(o["response"]["body"], latency)
                    r.raw["batch_id"] = batch.id
                    results[o["custom_id"]] = r
                else:
                    results[o["custom_id"]] = LLMResult("", None, None, None, latency, {"batch_id": batch.id},
                                                        error=json.dumps(o.get("error") or o.get("response")))
        return [results.get(f"r{i}", LLMResult("", None, None, None, latency, {"batch_id": batch.id},
                                                error=f"batch {batch.status}: sonuç yok")) for i in range(len(reqs))]


class OpenAICompatProvider(OpenAIProvider):
    """OpenAI uyumlu yerel sunucu (Ollama / vLLM). Açık ağırlıklı modeller için."""
    name = "openai_compat"
    supports_batch = False

    def _make_client(self, cls):
        env = self.spec.base_url_env or "LOCAL_BASE_URL"
        base_url = os.environ.get(env)
        if not base_url:
            raise RuntimeError(f"{env} tanımlı değil (.env). Ör. http://localhost:11434/v1")
        # CPU sunucularda tek çağrı dakikalar sürebilir: zaman aşımı yapılandırılabilir (varsayılan 30 dk)
        return cls(base_url=base_url, api_key=os.environ.get("LOCAL_API_KEY", "local"), max_retries=0,
                   timeout=float(getattr(self.spec, "timeout_s", None) or 1800))
