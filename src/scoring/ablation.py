"""Ablasyon: tüm koşulların ölçüt puanlarını aynı altın sette ve aynı katlarla üretir.

Koşullar (LLM çağrıları paylaşılır; yalnızca birleştirme biçimi değişir):
  1. single_zeroshot:<model>   Tek model, çapasız (K1 çapasız)
  2. single_anchored:<model>   Tek model, çapalı (K1 çapalı)
  3. panel_vote                K1 çapalı + ortalama, revizyon yok (Verga ve ark. tarzı)
  4. full_zeroshot             K1+K2 çapasız + öğrenilmiş ağırlık
  5. full_no_revision          K1 çapalı + öğrenilmiş ağırlık (revizyon katmanı yok)
  6. full_equal_weight         K2 çapalı + eşit ağırlık (ortalama)
  7. full                      K1+K2 çapalı + öğrenilmiş ağırlık (tüm katmanlar)
     full_median               K2 çapalı + ortanca               (Katman 3b)
     full_llm_aggregator       K2 çapalı + birleştirici LLM       (Katman 3a)
  8. embedding                 Gömme tabanlı puanlama
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .aggregation import cv_learned_weights, simple_aggregate, weight_variability
from .config import ItemBank
from .data import criteria_frame

CONDITION_ORDER = ["single_zeroshot", "single_anchored", "panel_vote", "full_zeroshot", "full_no_revision",
                   "full_equal_weight", "full", "full_median", "full_llm_aggregator", "embedding",
                   "embedding_tfidf_demo"]


def _wide(raw: pd.DataFrame, variant: str, layer: int, base: pd.DataFrame, models: list[str]):
    r = raw[(raw.variant == variant) & (raw.layer == layer)]
    if r.empty:
        return None, None
    s = r.pivot_table(index=["response_id", "criterion_id"], columns="model_key", values="score", aggfunc="first")
    c = r.pivot_table(index=["response_id", "criterion_id"], columns="model_key", values="call_id", aggfunc="first")
    cols = [m for m in models if m in s.columns]
    w = base.merge(s[cols].reset_index(), on=["response_id", "criterion_id"], how="left")
    cid = base[["response_id", "criterion_id"]].merge(c[cols].reset_index(), on=["response_id", "criterion_id"], how="left")
    return w, cid


def _join_ids(cid: pd.DataFrame, cols: list[str]) -> pd.Series:
    return cid[cols].apply(lambda r: ";".join(str(x) for x in r if isinstance(x, str) and x), axis=1)


def build_condition_scores(raw: pd.DataFrame, consensus: pd.DataFrame, folds: pd.DataFrame,
                           responses: pd.DataFrame, bank: ItemBank, scorers: list[str], aggregator: str,
                           rounding: str, weights_level: str, replicate: int = 1,
                           embedding_preds: pd.DataFrame | None = None,
                           embedding_condition: str = "embedding") -> tuple[pd.DataFrame, pd.DataFrame]:
    gold_ids = set(folds.response_id)
    raw = raw[(raw.replicate == replicate) & raw.score.notna() & raw.response_id.isin(gold_ids)]
    crit = criteria_frame(bank)
    base = (consensus[["response_id", "criterion_id", "consensus"]].rename(columns={"consensus": "y"})
            .merge(responses[["response_id", "item_id"]], on="response_id")
            .merge(crit[["item_id", "criterion_id", "score_min", "score_max"]], on=["item_id", "criterion_id"]))
    base = base[base.response_id.isin(gold_ids)].reset_index(drop=True)
    out: list[pd.DataFrame] = []
    weights_all: list[pd.DataFrame] = []

    def emit(name: str, scores: pd.Series, ids: pd.Series):
        out.append(pd.DataFrame({"condition": name, "response_id": base.response_id, "item_id": base.item_id,
                                 "criterion_id": base.criterion_id, "score": scores.values, "call_ids": ids.values}))

    for variant, prefix in (("zeroshot", "single_zeroshot"), ("anchored", "single_anchored")):
        w, cid = _wide(raw, variant, 1, base, scorers)
        if w is None:
            continue
        for m in scorers:
            if m in w:
                emit(f"{prefix}:{m}", w[m].astype(float), cid[m].fillna(""))

    l1a, l1a_id = _wide(raw, "anchored", 1, base, scorers)
    l2a, l2a_id = _wide(raw, "anchored", 2, base, scorers)
    l2z, l2z_id = _wide(raw, "zeroshot", 2, base, scorers)

    def learned(name, w, cid):
        cols = [m for m in scorers if m in w]
        pred, wts = cv_learned_weights(w, cols, folds, weights_level, rounding)
        emit(name, pred, _join_ids(cid, cols))
        weights_all.append(wts.assign(condition=name))

    if l1a is not None:
        cols = [m for m in scorers if m in l1a]
        emit("panel_vote", simple_aggregate(l1a, cols, "mean", rounding), _join_ids(l1a_id, cols))
        learned("full_no_revision", l1a, l1a_id)
    if l2z is not None:
        learned("full_zeroshot", l2z, l2z_id)
    if l2a is not None:
        cols = [m for m in scorers if m in l2a]
        emit("full_equal_weight", simple_aggregate(l2a, cols, "mean", rounding), _join_ids(l2a_id, cols))
        emit("full_median", simple_aggregate(l2a, cols, "median", rounding), _join_ids(l2a_id, cols))
        learned("full", l2a, l2a_id)
    l3, l3_id = _wide(raw, "anchored", 3, base, [aggregator])
    if l3 is not None and aggregator in l3:
        emit("full_llm_aggregator", l3[aggregator].astype(float), l3_id[aggregator].fillna(""))
    if embedding_preds is not None and len(embedding_preds):
        e = base[["response_id", "criterion_id"]].merge(embedding_preds, on=["response_id", "criterion_id"], how="left")
        emit(embedding_condition, e.pred.astype(float), e.call_id.fillna(""))

    cond = pd.concat(out, ignore_index=True)
    weights = pd.concat(weights_all, ignore_index=True) if weights_all else pd.DataFrame()
    return cond, weights


def summarize_weights(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return weights
    parts = [weight_variability(g).assign(condition=c) for c, g in weights.groupby("condition")]
    return pd.concat(parts)[["condition", "group", "model_key", "mean", "sd", "min", "max"]]


def condition_sort_key(name: str) -> tuple[int, str]:
    base = name.split(":")[0]
    return (CONDITION_ORDER.index(base) if base in CONDITION_ORDER else 99, name)
