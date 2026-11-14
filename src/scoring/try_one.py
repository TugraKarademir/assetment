"""Tek bir yanıtı katmanlı çerçeveyle puanlama (arayüz ve hızlı deneme için).

- Yapıştırılan metin önce genel kişisel veri maskesinden geçer (e-posta, telefon, numara, yaygın adlar).
- Çağrılar diğer tüm çalıştırmalar gibi logs/<run_id>/calls.jsonl dosyasına kaydedilir ve önbelleğe girer.
- Sonuçlar ham puan deposuna (raw_scores.csv) YAZILMAZ: denemeler araştırma verisine karışmaz.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .anonymize import PIIMasker, _read_list
from .config import load_experiment, load_items, load_models
from .manifest import new_run_id, write_manifest
from .pipeline import CONDITION_PLANS, run_pipeline
from .utils import round_score, sha256_text


@dataclass
class TrialResult:
    run_id: str
    item_id: str
    response_id: str
    masked_text: str
    n_masked: int
    rows: pd.DataFrame            # katman × model × ölçüt puanları ve gerekçeler
    summary: pd.DataFrame         # ölçüt başına: K1/K2 model puanları + ortalama, ortanca, birleştirici
    notes: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def mask_text(text: str) -> tuple[str, int]:
    masker = PIIMasker([], [], [], denylist=_read_list("config/pii_denylist.txt"),
                       common_first_names=_read_list("config/tr_first_names.txt"),
                       ambiguous_words=_read_list("config/pii_ambiguous_words.txt"))
    masked, findings = masker.mask(text)
    return masked, sum(f.masked for f in findings)


def score_single(item_id: str, text: str, models_path: str | Path = "config/models.yaml",
                 max_layer: int = 3) -> TrialResult:
    exp, bank, models = load_experiment(), load_items(), load_models(models_path)
    item = bank[item_id]
    masked, n_masked = mask_text(text.strip())
    rid = "DENEME-" + sha256_text(masked)[:8].upper()
    responses = pd.DataFrame([{"response_id": rid, "student_code": "DENEME", "item_id": item_id, "text": masked,
                               "is_empty": False}])
    run_id = new_run_id("ui")
    write_manifest(run_id, exp.path("logs_dir"), exp.path("results_dir"),
                   ["config/items.yaml", str(models_path), "config/experiment.yaml"], exp.seeds,
                   {"condition": "ui_trial", "item_id": item_id, "response_id": rid,
                    "models": models.model_dump(mode="json")}, copy_to_results=False)
    rows, notes = asyncio.run(run_pipeline(responses, bank, models, exp, CONDITION_PLANS["full"], 1, run_id,
                                           "ui_trial", use_batch=False, max_layer=max_layer))
    errors = sorted({f"{r.model_key} (K{int(r.layer)}): {r.error}" for r in rows[rows.score.isna()].itertuples()})
    ok = rows[rows.score.notna()].copy()
    ok["score"] = ok.score.astype(int)

    rule = exp.aggregation["rounding"]
    recs = []
    for c in item.criteria:
        rec = {"Ölçüt": f"{c.criterion_id} – {c.name}", "Aralık": f"{c.score_min}–{c.score_max}"}
        for layer, tag in ((1, "K1"), (2, "K2")):
            for mk in models.scorers:
                v = ok[(ok.layer == layer) & (ok.model_key == mk) & (ok.criterion_id == c.criterion_id)].score
                rec[f"{tag} {mk}"] = int(v.iloc[0]) if len(v) else None
        last = max([lyr for lyr in (1, 2) if any(rec.get(f"K{lyr} {m}") is not None for m in models.scorers)],
                   default=None)
        vals = [rec[f"K{last} {m}"] for m in models.scorers if last and rec.get(f"K{last} {m}") is not None]
        rec["Ortalama"] = round_score(sum(vals) / len(vals), rule) if vals else None
        rec["Ortanca"] = round_score(float(pd.Series(vals).median()), rule) if vals else None
        agg = ok[(ok.layer == 3) & (ok.criterion_id == c.criterion_id)].score
        rec["Birleştirici LLM"] = int(agg.iloc[0]) if len(agg) else None
        recs.append(rec)
    summary = pd.DataFrame(recs)
    num = [c for c in summary.columns if c not in ("Ölçüt", "Aralık")]
    total = {"Ölçüt": "TOPLAM", "Aralık": f"{item.total_min}–{item.total_max}"}
    for c in num:
        col = summary[c]
        total[c] = int(col.sum()) if col.notna().all() else None
    summary = pd.concat([summary, pd.DataFrame([total])], ignore_index=True)
    return TrialResult(run_id, item_id, rid, masked, n_masked, ok, summary, notes, errors)
