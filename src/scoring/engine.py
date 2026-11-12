"""Çağrı motoru: önbellek, JSONL çağrı kaydı, eşzamanlılık, üstel geri çekilme, batch, doğrulama yeniden denemesi.

Her model çağrısı (önbellekten gelenler dahil) logs/<run_id>/calls.jsonl dosyasına bir satır olarak yazılır.
Önbellek anahtarı = SHA-256(sağlayıcı, model, sistem istemi, mesajlar, etkin parametreler, replikasyon).
Aynı anahtar için model yeniden çağrılmaz; yarıda kesilen çalıştırma yeniden başlatıldığında kaldığı yerden
devam eder (tamamlanan çağrılar önbellekten okunur).
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import ModelsConfig
from .providers import LLMRequest, LLMResult, Provider, RetryableError, effective_params, make_provider
from .utils import ensure_parent, sha256_text, stable_json

Validator = Callable[[str], tuple[Any | None, str | None]]

CORRECTION_PROMPT = ("Önceki çıktın geçersizdi: {error}\n"
                     "Lütfen YALNIZCA istenen şemaya uyan geçerli bir JSON nesnesi döndür; başka metin ekleme.")


# ----------------------------------------------------------------------------- önbellek
class Cache:
    def __init__(self, path: str | Path):
        self.path = ensure_parent(path)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, call_id TEXT, run_id TEXT,"
                          " created_at TEXT, payload TEXT)")
        self.conn.commit()

    def get(self, key: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT call_id, run_id, payload FROM calls WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        return {"call_id": row[0], "run_id": row[1], **json.loads(row[2])}

    def put(self, key: str, call_id: str, run_id: str, payload: dict) -> None:
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?)",
                              (key, call_id, run_id, datetime.now(timezone.utc).isoformat(),
                               json.dumps(payload, ensure_ascii=False)))
            self.conn.commit()


# ----------------------------------------------------------------------------- kayıt
class CallLogger:
    def __init__(self, path: str | Path):
        self.path = ensure_parent(path)
        self._lock = threading.Lock()

    def write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def load_call_ids(logs_dir: str | Path) -> set[str]:
    """Tüm çalıştırma kayıtlarındaki çağrı kimlikleri (raporlanan sonuçların kaydı var mı denetimi için)."""
    ids: set[str] = set()
    for p in Path(logs_dir).glob("*/calls.jsonl"):
        with open(p, encoding="utf-8") as f:
            for ln in f:
                try:
                    ids.add(json.loads(ln)["call_id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return ids


# ----------------------------------------------------------------------------- motor
@dataclass
class Job:
    request: LLMRequest
    validate: Validator


@dataclass
class Outcome:
    job: Job
    parsed: Any | None = None
    call_id: str | None = None
    call_ids: list[str] = field(default_factory=list)
    error: str | None = None


class CallEngine:
    def __init__(self, models: ModelsConfig, run_id: str, cache_path: str | Path, logs_dir: str | Path,
                 use_batch: bool = True, batch_poll_seconds: float = 30):
        self.models = models
        self.run_id = run_id
        self.cache = Cache(cache_path)
        self.logger = CallLogger(Path(logs_dir) / run_id / "calls.jsonl")
        self.use_batch = use_batch
        self.batch_poll_seconds = batch_poll_seconds
        self._providers: dict[str, Provider] = {}
        self._sems: dict[str, asyncio.Semaphore] = {}
        self.stats = defaultdict(int)

    def provider(self, key: str) -> Provider:
        if key not in self._providers:
            self._providers[key] = make_provider(self.models.spec(key))
            self._sems[key] = asyncio.Semaphore(self.models.spec(key).max_concurrency)
        return self._providers[key]

    def cache_key(self, req: LLMRequest) -> str:
        spec = self.models.spec(req.model_key)
        return sha256_text(stable_json({"provider": spec.provider, "model": spec.model, "system": req.system,
                                        "messages": req.messages, "params": effective_params(spec),
                                        "replicate": req.metadata.get("replicate", 1)}))

    # -- tek çağrı (geri çekilmeli) ---------------------------------------------
    async def _call_one(self, req: LLMRequest) -> LLMResult:
        prov = self.provider(req.model_key)
        r = self.models.retry
        async with self._sems[req.model_key]:
            try:
                async for attempt in AsyncRetrying(
                        retry=retry_if_exception_type(RetryableError),
                        wait=wait_exponential_jitter(initial=r.backoff_initial_seconds, max=r.backoff_max_seconds),
                        stop=stop_after_attempt(r.max_api_retries), reraise=True):
                    with attempt:
                        if attempt.retry_state.attempt_number > 1:
                            self.stats["api_retries"] += 1
                        return await prov.complete(req)
            except Exception as e:  # kalıcı hata: kaydedilir, çalıştırma durmaz
                return LLMResult("", None, None, None, 0.0, error=f"{type(e).__name__}: {e}")
        raise AssertionError("unreachable")

    async def _send(self, reqs: list[LLMRequest]) -> list[tuple[LLMResult, bool, str | None, str]]:
        """İstekleri gönderir; (sonuç, önbellekten_mi, kaynak_call_id, anahtar) döndürür."""
        out: list = [None] * len(reqs)
        by_model: dict[str, list[int]] = defaultdict(list)
        for i, rq in enumerate(reqs):
            key = self.cache_key(rq)
            hit = self.cache.get(key)
            if hit:
                res = LLMResult(hit["text"], hit.get("input_tokens"), hit.get("output_tokens"),
                                hit.get("model_version_returned"), hit.get("latency_s", 0.0), hit.get("raw", {}))
                out[i] = (res, True, hit["call_id"], key)
                self.stats["cache_hits"] += 1
            else:
                by_model[rq.model_key].append(i)

        async def run_model(mk: str, idx: list[int]):
            prov = self.provider(mk)
            spec = self.models.spec(mk)
            if self.use_batch and spec.batch and prov.supports_batch and len(idx) > 1:
                try:
                    results = await prov.complete_batch([reqs[i] for i in idx], self.batch_poll_seconds)
                except Exception as e:
                    results = [LLMResult("", None, None, None, 0.0, error=f"batch: {type(e).__name__}: {e}")] * len(idx)
                self.stats["batch_requests"] += len(idx)
            else:
                results = await asyncio.gather(*(self._call_one(reqs[i]) for i in idx))
            for i, res in zip(idx, results):
                out[i] = (res, False, None, self.cache_key(reqs[i]))

        await asyncio.gather(*(run_model(mk, idx) for mk, idx in by_model.items()))
        return out

    # -- kayıt satırı -------------------------------------------------------------
    def _log(self, req: LLMRequest, res: LLMResult, cache_hit: bool, source_call_id: str | None, key: str,
             parsed: Any, validation_error: str | None) -> str:
        spec = self.models.spec(req.model_key)
        call_id = source_call_id if cache_hit else uuid.uuid4().hex
        cost = None
        if res.input_tokens is not None and res.output_tokens is not None:
            cost = (res.input_tokens * spec.price_input_per_mtok + res.output_tokens * spec.price_output_per_mtok) / 1e6
        meta = {k: None for k in ("condition", "layer", "variant", "item_id", "response_id", "replicate",
                                  "template_name", "template_sha256", "attempt")}
        meta.update({k: v for k, v in req.metadata.items() if k != "mock"})
        prompt = req.prompt_text()
        self.logger.write({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "call_id": call_id,
            "log_entry_id": uuid.uuid4().hex,
            "cache_hit": cache_hit,
            "cache_key": key,
            **meta,
            "model_key": req.model_key,
            "provider": spec.provider,
            "model_requested": spec.model,
            "model_version_returned": res.model_version_returned,
            "params": effective_params(spec),
            "prompt_sha256": sha256_text(prompt),
            "prompt_text": prompt,
            "raw_response": res.text,
            "provider_raw": res.raw,
            "parsed_output": parsed,
            "validation_error": validation_error,
            "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens,
            "latency_s": round(res.latency_s, 3),
            "cost_usd_est": None if cost is None else (0.0 if cache_hit else round(cost, 6)),
            "error": res.error,
        })
        if not cache_hit and res.error is None:
            self.cache.put(key, call_id, self.run_id, {
                "text": res.text, "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                "model_version_returned": res.model_version_returned, "latency_s": res.latency_s, "raw": res.raw})
        if not cache_hit:
            self.stats["api_calls"] += 1
            self.stats["cost_usd_est"] += cost or 0.0
        return call_id

    # -- doğrulamalı toplu yürütme ------------------------------------------------
    async def run(self, jobs: list[Job]) -> list[Outcome]:
        max_retries = self.models.retry.max_validation_retries
        outcomes = [Outcome(job=j) for j in jobs]
        pending = list(range(len(jobs)))
        reqs = {i: jobs[i].request for i in pending}
        for attempt in range(max_retries + 1):
            if not pending:
                break
            for i in pending:
                reqs[i].metadata["attempt"] = attempt
            results = await self._send([reqs[i] for i in pending])
            nxt = []
            for i, (res, hit, src, key) in zip(pending, results):
                parsed, verr = (None, None)
                if res.error is None:
                    parsed, verr = jobs[i].validate(res.text)
                call_id = self._log(reqs[i], res, hit, src, key, parsed, verr)
                outcomes[i].call_ids.append(call_id)
                if res.error is not None:
                    outcomes[i].error = f"api: {res.error}"
                    self.stats["api_errors"] += 1
                elif verr is None:
                    outcomes[i].parsed, outcomes[i].call_id, outcomes[i].error = parsed, call_id, None
                else:
                    outcomes[i].error = f"validation: {verr}"
                    self.stats["validation_failures"] += 1
                    if attempt < max_retries:
                        r = reqs[i]
                        reqs[i] = LLMRequest(r.model_key, r.system, [*r.messages,
                                             {"role": "assistant", "content": res.text or "(boş)"},
                                             {"role": "user", "content": CORRECTION_PROMPT.format(error=verr)}],
                                             dict(r.metadata))
                        nxt.append(i)
            pending = nxt
        for o in outcomes:
            if o.parsed is None:
                self.stats["final_failures"] += 1
        return outcomes
