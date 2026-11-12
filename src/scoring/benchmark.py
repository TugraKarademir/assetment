"""CPU sunucuları için hız ölçümü ve iş yükü/süre tahmini.

Ölçüm: her modele gerçek (Katman 1, çapalı) istemler, modelin `max_concurrency` değeri kadar eşzamanlı
gönderilir; modeller ayrı sunucularda olduğundan aynı anda ölçülür. Etkin süre = duvar saati / çağrı sayısı.
Ölçüm çağrıları kayda yazılır ama önbellek anahtarına özel bir replikasyon etiketi eklenerek gerçek
puanlamayla karışmaz.

Tahmin: katmanlar sırayla yürür; bir katmanda puanlayıcılar ayrı sunucularda PARALEL çalışır, dolayısıyla
katman süresi en yavaş puanlayıcının süresidir. Birleştirici yalnızca Katman 3'te çalışır.
"""
from __future__ import annotations

import asyncio
import time

import pandas as pd

from .config import ItemBank, ModelsConfig
from .engine import CallEngine
from .layers import PromptRenderer, build_layer1_jobs

RETRY_OVERHEAD = 1.05  # doğrulama yeniden denemeleri için pay


async def measure(responses: pd.DataFrame, bank: ItemBank, models: ModelsConfig, engine: CallEngine,
                  renderer: PromptRenderer, run_id: str) -> pd.DataFrame:
    keys = [*models.scorers, models.aggregator]
    jobs = build_layer1_jobs(responses, bank, keys, "anchored", replicate=1, renderer=renderer, condition="benchmark")
    for j in jobs:
        j.request.metadata["replicate"] = f"bench-{run_id}"   # önbellekte gerçek puanlarla karışmasın

    async def one(mk: str):
        js = [j for j in jobs if j.request.model_key == mk]
        t0 = time.perf_counter()
        outs = await engine.run(js)
        wall = time.perf_counter() - t0
        return mk, js, outs, wall

    rows = []
    for mk, js, outs, wall in await asyncio.gather(*(one(k) for k in keys)):
        ok = [o for o in outs if o.parsed is not None]
        spec = models.spec(mk)
        rows.append({"model_key": mk, "model": spec.model, "server": getattr(spec, "served_by", ""),
                     "calls": len(js), "valid": len(ok), "concurrency": spec.max_concurrency,
                     "wall_s": round(wall, 1), "sec_per_call": round(wall / max(1, len(js)), 1),
                     "first_error": next((o.error for o in outs if o.parsed is None), "")[:120]})
    return pd.DataFrame(rows)


def workload(n_gold: int, n_all: int, scorers: list[str], aggregator: str, condition: str = "ablation",
             stability: bool = True, operational: bool = True) -> pd.DataFrame:
    """Aşama × katman × model çağrı sayıları."""
    rows = []
    l2z = condition == "ablation"
    for layer, n in (("K1 çapalı", n_gold), ("K1 çapasız", n_gold), ("K2 çapalı", n_gold),
                     *((("K2 çapasız", n_gold),) if l2z else ())):
        rows += [{"aşama": f"ablasyon ({condition})", "katman": layer, "model_key": m, "calls": n} for m in scorers]
    rows.append({"aşama": f"ablasyon ({condition})", "katman": "K3 birleştirici", "model_key": aggregator, "calls": n_gold})
    if stability:
        rows += [{"aşama": "kararlılık (2. puanlama)", "katman": "K1 çapalı", "model_key": m, "calls": n_gold}
                 for m in scorers]
    if operational and n_all > n_gold:
        rest = n_all - n_gold
        for layer in ("K1 çapalı", "K2 çapalı"):
            rows += [{"aşama": "operasyonel (altın set dışı)", "katman": layer, "model_key": m, "calls": rest}
                     for m in scorers]
        rows.append({"aşama": "operasyonel (altın set dışı)", "katman": "K3 birleştirici", "model_key": aggregator,
                     "calls": rest})
    return pd.DataFrame(rows)


def project(work: pd.DataFrame, speed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Katman başına duvar saati (paralel sunucular: en yavaş model) ve aşama toplamları."""
    spc = speed.set_index("model_key").sec_per_call
    w = work.copy()
    w["hours"] = w.calls * w.model_key.map(spc) * RETRY_OVERHEAD / 3600
    layer = (w.groupby(["aşama", "katman"], sort=False)
             .agg(calls=("calls", "sum"), wall_hours=("hours", "max"),
                  bottleneck=("hours", lambda h: w.loc[h.idxmax(), "model_key"])).reset_index())
    phase = layer.groupby("aşama", sort=False).agg(calls=("calls", "sum"), wall_hours=("wall_hours", "sum")).reset_index()
    phase["wall_days"] = phase.wall_hours / 24
    total = pd.DataFrame([{"aşama": "TOPLAM", "calls": phase.calls.sum(), "wall_hours": phase.wall_hours.sum(),
                           "wall_days": phase.wall_hours.sum() / 24}])
    return layer, pd.concat([phase, total], ignore_index=True)
