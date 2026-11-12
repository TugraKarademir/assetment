"""Anthropic Claude (Messages API ve Message Batches API).

Not: Güncel API sürümü temperature/top_p/top_k kabul etmez (gönderilirse 400). Bu sağlayıcıda sıcaklık
gönderilmez; kayıtta "unsupported" olarak işaretlenir. Tutarlılık için `effort` düşük tutulur ve
istemde yalnızca JSON istenir. Model içi kararlılık ayrıca ölçülür (stability).
"""
from __future__ import annotations

import asyncio
import os
import time

from .base import LLMRequest, LLMResult, Provider, RetryableError


class AnthropicProvider(Provider):
    name = "anthropic"
    supports_batch = True
    supported_sampling = ()

    def __init__(self, spec):
        super().__init__(spec)
        import anthropic
        self._anthropic = anthropic
        self.client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), max_retries=0)

    def _params(self, req: LLMRequest) -> dict:
        p = self.spec.params
        params = {"model": self.spec.model, "max_tokens": p.get("max_tokens", 4000), "system": req.system,
                  "messages": req.messages}
        if p.get("effort"):
            params["output_config"] = {"effort": p["effort"]}
        return params

    @staticmethod
    def _parse(msg, latency: float) -> LLMResult:
        if msg.stop_reason == "refusal":
            return LLMResult("", msg.usage.input_tokens, msg.usage.output_tokens, msg.model, latency,
                             {"id": msg.id, "stop_reason": msg.stop_reason}, error="refusal")
        text = "".join(b.text for b in msg.content if b.type == "text")
        return LLMResult(text, msg.usage.input_tokens, msg.usage.output_tokens, msg.model, latency,
                         {"id": msg.id, "stop_reason": msg.stop_reason})

    async def complete(self, req: LLMRequest) -> LLMResult:
        a = self._anthropic
        t0 = time.perf_counter()
        try:
            msg = await self.client.messages.create(**self._params(req))
        except (a.RateLimitError, a.APITimeoutError, a.APIConnectionError, a.InternalServerError) as e:
            raise RetryableError(f"{type(e).__name__}: {e}") from e
        return self._parse(msg, time.perf_counter() - t0)

    async def complete_batch(self, reqs: list[LLMRequest], poll_seconds: float = 30) -> list[LLMResult]:
        batch = await self.client.messages.batches.create(
            requests=[{"custom_id": f"r{i}", "params": self._params(r)} for i, r in enumerate(reqs)])
        t0 = time.perf_counter()
        while batch.processing_status != "ended":
            await asyncio.sleep(poll_seconds)
            batch = await self.client.messages.batches.retrieve(batch.id)
        latency = time.perf_counter() - t0
        out: dict[str, LLMResult] = {}
        async for res in await self.client.messages.batches.results(batch.id):
            if res.result.type == "succeeded":
                r = self._parse(res.result.message, latency)
            else:
                r = LLMResult("", None, None, None, latency, error=f"batch:{res.result.type}")
            r.raw["batch_id"] = batch.id
            out[res.custom_id] = r
        return [out.get(f"r{i}", LLMResult("", None, None, None, latency, {"batch_id": batch.id},
                                           error="batch: sonuç yok")) for i in range(len(reqs))]
