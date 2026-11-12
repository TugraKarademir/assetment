"""Sağlayıcı soyutlaması: tüm modeller bu arayüz üzerinden çağrılır."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import ModelSpec


class RetryableError(RuntimeError):
    """Hız sınırı, zaman aşımı, 5xx gibi yeniden denenebilir hatalar."""


@dataclass
class LLMRequest:
    model_key: str
    system: str
    messages: list[dict[str, str]]          # [{"role": "user"|"assistant", "content": str}]
    metadata: dict[str, Any] = field(default_factory=dict)

    def prompt_text(self) -> str:
        parts = [f"[system]\n{self.system}"] + [f"[{m['role']}]\n{m['content']}" for m in self.messages]
        return "\n\n".join(parts)


@dataclass
class LLMResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    model_version_returned: str | None
    latency_s: float
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Provider:
    name = "base"
    supports_batch = False
    # Sağlayıcının kabul ettiği örnekleme parametreleri; diğerleri gönderilmez ve kayıtta işaretlenir
    supported_sampling = ("temperature", "seed")

    def __init__(self, spec: ModelSpec):
        self.spec = spec

    @classmethod
    def effective_params_for(cls, spec: ModelSpec) -> dict[str, Any]:
        """Kayıt için: gerçekten gönderilen parametreler ve desteklenmeyenler."""
        p = dict(spec.params)
        out = {k: v for k, v in p.items() if k not in ("temperature", "seed") or k in cls.supported_sampling}
        for k in ("temperature", "seed"):
            if k in p and k not in cls.supported_sampling:
                out[k] = f"unsupported (yapılandırmada {p[k]}; gönderilmedi)"
        return out

    def effective_params(self) -> dict[str, Any]:
        return self.effective_params_for(self.spec)

    async def complete(self, req: LLMRequest) -> LLMResult:  # pragma: no cover - arayüz
        raise NotImplementedError

    async def complete_batch(self, reqs: list[LLMRequest], poll_seconds: float = 30) -> list[LLMResult]:
        raise NotImplementedError(f"{self.name} toplu (batch) çağrıyı desteklemiyor")
