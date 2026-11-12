"""Çalıştırma orkestrasyonu: koşul -> gerekli LLM katmanları -> çağrı motoru -> ham puan deposu."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import Experiment, ItemBank, ModelsConfig
from .engine import CallEngine
from .layers import (ROW_COLUMNS, LayerPlan, PromptRenderer, build_layer1_jobs, build_layer2_jobs,
                     build_layer3_jobs, outcomes_to_rows)
from .utils import ensure_parent

# Koşul -> gereken LLM çağrı grupları
CONDITION_PLANS: dict[str, LayerPlan] = {
    "single_zeroshot": LayerPlan(False, True, False, False, False),
    "single_anchored": LayerPlan(True, False, False, False, False),
    "panel_vote": LayerPlan(True, False, False, False, False),
    "full_no_revision": LayerPlan(True, False, False, False, False),
    "full_zeroshot": LayerPlan(False, True, False, True, False),
    "full_equal_weight": LayerPlan(True, False, True, False, False),
    "full_median": LayerPlan(True, False, True, False, False),
    "full_llm_aggregator": LayerPlan(True, False, True, False, True),
    "full": LayerPlan(True, False, True, False, True),
    "ablation": LayerPlan(True, True, True, True, True),
    "stability": LayerPlan(True, False, False, False, False),
}
KEY_COLS = ["replicate", "variant", "layer", "model_key", "response_id", "criterion_id"]


def load_raw_scores(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=ROW_COLUMNS)
    return pd.read_csv(p, dtype={"response_id": str, "call_id": str, "criterion_id": str})


def store_raw_scores(path: str | Path, new: pd.DataFrame) -> pd.DataFrame:
    """Depoya ekler; aynı anahtar için en son satır kalır. Hatalı (puansız) satırlar ayrıca korunur."""
    old = load_raw_scores(path)
    both = pd.concat([old, new], ignore_index=True) if len(old) else new.copy()
    ok = both[both.score.notna()].drop_duplicates(KEY_COLS, keep="last")
    # Sonradan başarılı olmuş bir çağrının eski hata satırını at
    err = both[both.score.isna()].drop_duplicates(["replicate", "variant", "layer", "model_key", "response_id"],
                                                  keep="last")
    done = set(zip(ok.replicate, ok.variant, ok.layer, ok.model_key, ok.response_id))
    err = err[[t not in done for t in zip(err.replicate, err.variant, err.layer, err.model_key, err.response_id)]]
    out = pd.concat([ok, err], ignore_index=True).sort_values(KEY_COLS)
    out.to_csv(ensure_parent(path), index=False)
    return out


async def run_pipeline(responses: pd.DataFrame, bank: ItemBank, models: ModelsConfig, exp: Experiment,
                       plan: LayerPlan, replicate: int, run_id: str, condition: str, use_batch: bool = True,
                       include_anchors_later_layers: bool = True, sequential_models: bool = False,
                       only_models: set[str] | None = None, max_layer: int = 3) -> tuple[pd.DataFrame, dict]:
    renderer = PromptRenderer()
    engine = CallEngine(models, run_id, exp.path("cache"), exp.path("logs_dir"), use_batch=use_batch,
                        sequential_models=sequential_models, only_models=only_models)
    full_panel = exp.aggregation.get("require_full_panel", True)
    seed = exp.seeds["layer2_order"]
    scorers = models.scorers
    all_rows: list[pd.DataFrame] = []
    notes: dict = {}

    async def run_jobs(jobs, label):
        if not jobs:
            return pd.DataFrame(columns=ROW_COLUMNS)
        outcomes = await engine.run(jobs)
        rows = outcomes_to_rows(outcomes, run_id)
        rows_store = rows[~rows.error.fillna("").str.startswith("cache-only")]
        notes[label] = {"jobs": len(jobs),
                        "failed": int(sum(o.parsed is None and not (o.error or "").startswith("cache-only")
                                          for o in outcomes)),
                        "cache_only_missing": int(sum((o.error or "").startswith("cache-only") for o in outcomes))}
        all_rows.append(rows_store)
        return rows

    variants = [v for v, on in (("anchored", plan.layer1_anchored or plan.layer2_anchored or plan.layer3),
                                ("zeroshot", plan.layer1_zeroshot or plan.layer2_zeroshot)) if on]
    l1: dict[str, pd.DataFrame] = {}
    for v in variants:
        l1[v] = await run_jobs(build_layer1_jobs(responses, bank, scorers, v, replicate, renderer, condition),
                               f"layer1_{v}")
    l2: dict[str, pd.DataFrame] = {}
    for v, on in (("anchored", plan.layer2_anchored or plan.layer3), ("zeroshot", plan.layer2_zeroshot)):
        if on and max_layer >= 2:
            jobs, skipped = build_layer2_jobs(responses, bank, l1[v], scorers, v, replicate, renderer, seed,
                                              include_anchors_later_layers, condition, full_panel)
            l2[v] = await run_jobs(jobs, f"layer2_{v}")
            notes[f"layer2_{v}_skipped"] = len(skipped)
    if plan.layer3 and max_layer >= 3:
        jobs, skipped = build_layer3_jobs(responses, bank, l2["anchored"], scorers, models.aggregator, "anchored",
                                          replicate, renderer, seed, include_anchors_later_layers, condition,
                                          full_panel)
        await run_jobs(jobs, "layer3_anchored")
        notes["layer3_skipped"] = len(skipped)

    new = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame(columns=ROW_COLUMNS)
    notes["engine_stats"] = dict(engine.stats)
    return new, notes


# ----------------------------------------------------------------------------- maliyet tahmini
def estimate_cost(responses: pd.DataFrame, bank: ItemBank, models: ModelsConfig, exp: Experiment,
                  plan: LayerPlan, replicate: int = 1) -> pd.DataFrame:
    """İstemleri gerçekten oluşturarak token sayısını tahmin eder; Katman 1 için önbellekteki çağrıları düşer."""
    renderer = PromptRenderer()
    cpt = exp.cost["chars_per_token"]
    out_tok = exp.cost["expected_output_tokens"]
    engine = CallEngine(models, "estimate", exp.path("cache"), exp.path("logs_dir"))
    rows = []

    def add(layer, variant, model_key, n_calls, in_tokens, cached):
        spec = models.spec(model_key)
        o = out_tok[f"layer{layer}"]
        billable = n_calls - cached
        cost = billable * (in_tokens * spec.price_input_per_mtok + o * spec.price_output_per_mtok) / 1e6
        if spec.batch:
            cost *= 0.5  # toplu API indirimi (sağlayıcıya göre değişebilir)
        rows.append({"layer": layer, "variant": variant, "model_key": model_key, "model": spec.model,
                     "calls": n_calls, "cached": cached, "avg_input_tokens": round(in_tokens),
                     "output_tokens_per_call": o, "batch": spec.batch, "est_cost_usd": round(cost, 2)})

    for v, on1, on2 in (("anchored", plan.layer1_anchored or plan.layer2_anchored or plan.layer3,
                         plan.layer2_anchored or plan.layer3),
                        ("zeroshot", plan.layer1_zeroshot or plan.layer2_zeroshot, plan.layer2_zeroshot)):
        if not on1:
            continue
        jobs = build_layer1_jobs(responses, bank, models.scorers, v, replicate, renderer)
        for mk in models.scorers:
            js = [j for j in jobs if j.request.model_key == mk]
            avg = sum(len(j.request.prompt_text()) for j in js) / max(1, len(js)) / cpt
            cached = sum(engine.cache.get(engine.cache_key(j.request)) is not None for j in js)
            add(1, v, mk, len(js), avg, cached)
            if on2:
                n_crit = sum(len(bank[i].criteria) for i in responses.item_id) / max(1, len(responses))
                extra = len(models.scorers) * n_crit * 70
                add(2, v, mk, len(js), avg + extra, 0)
        if v == "anchored" and plan.layer3:
            js = [j for j in jobs if j.request.model_key == models.scorers[0]]
            avg = sum(len(j.request.prompt_text()) for j in js) / max(1, len(js)) / cpt
            add(3, v, models.aggregator, len(js), avg + len(models.scorers) * 3 * 60, 0)
    return pd.DataFrame(rows)
