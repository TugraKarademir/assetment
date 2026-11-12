"""Google Gemini (google-genai SDK)."""
from __future__ import annotations

import os
import time

from .base import LLMRequest, LLMResult, Provider, RetryableError


class GoogleProvider(Provider):
    name = "google"
    supports_batch = False

    def __init__(self, spec):
        super().__init__(spec)
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

    async def complete(self, req: LLMRequest) -> LLMResult:
        t = self.types
        p = self.spec.params
        cfg = t.GenerateContentConfig(system_instruction=req.system, temperature=p.get("temperature"),
                                      seed=p.get("seed"), max_output_tokens=p.get("max_tokens", 4000),
                                      response_mime_type="application/json")
        contents = [t.Content(role="user" if m["role"] == "user" else "model", parts=[t.Part(text=m["content"])])
                    for m in req.messages]
        t0 = time.perf_counter()
        try:
            resp = await self.client.aio.models.generate_content(model=self.spec.model, contents=contents, config=cfg)
        except Exception as e:  # google-genai hata sınıfları sürüme göre değişir
            code = getattr(e, "code", None) or getattr(e, "status_code", None)
            if code in (429, 500, 502, 503, 504) or "RESOURCE_EXHAUSTED" in str(e):
                raise RetryableError(str(e)) from e
            raise
        um = resp.usage_metadata
        return LLMResult(resp.text or "", getattr(um, "prompt_token_count", None),
                         getattr(um, "candidates_token_count", None), resp.model_version or self.spec.model,
                         time.perf_counter() - t0, {"response_id": resp.response_id})
