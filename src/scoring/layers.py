"""Katman 1 (bağımsız puanlama), Katman 2 (revizyon), Katman 3(a) (LLM birleştirici)."""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import Item, ItemBank, ModelsConfig
from .engine import Job, Outcome
from .providers import LLMRequest
from .schemas import RevisionOutput, ScoreOutput, make_validator
from .utils import sha256_text

TEMPLATES = {("layer1", "anchored"): "layer1_score.j2", ("layer1", "zeroshot"): "layer1_score_zeroshot.j2",
             ("layer2", "anchored"): "layer2_revise.j2", ("layer2", "zeroshot"): "layer2_revise.j2",
             ("layer3", "anchored"): "layer3_aggregate.j2", ("layer3", "zeroshot"): "layer3_aggregate.j2"}
ROW_COLUMNS = ["run_id", "replicate", "variant", "layer", "model_key", "item_id", "response_id", "criterion_id",
               "score", "rationale", "rubric_evidence", "confidence", "changed", "total_mismatch", "call_id", "error"]


class PromptRenderer:
    SPLIT = "=== USER ==="

    def __init__(self, prompts_dir: str | Path = "prompts", rationale_style: str = "standard"):
        if rationale_style not in ("short", "standard"):
            raise ValueError(f"rationale_style 'short' ya da 'standard' olmalı: {rationale_style}")
        self.dir = Path(prompts_dir)
        self.env = Environment(loader=FileSystemLoader(str(self.dir)), undefined=StrictUndefined,
                               trim_blocks=False, lstrip_blocks=False, keep_trailing_newline=True)
        self.env.globals["rationale_style"] = rationale_style

    def template_sha(self, name: str) -> str:
        src = (self.dir / name).read_text(encoding="utf-8") + (self.dir / "_common.j2").read_text(encoding="utf-8")
        return sha256_text(src)

    def render(self, name: str, **ctx) -> tuple[str, str]:
        text = self.env.get_template(name).render(**ctx)
        if self.SPLIT not in text:
            raise ValueError(f"{name}: '{self.SPLIT}' ayırıcısı yok")
        system, user = text.split(self.SPLIT, 1)
        return system.strip(), user.strip()


def _criteria_ranges(item: Item) -> dict[str, tuple[int, int]]:
    return {c.criterion_id: (c.score_min, c.score_max) for c in item.criteria}


def _anchor_dicts(item: Item) -> list[dict]:
    return [{"text": a.text, "scores": a.scores} for a in item.anchors]


def _meta(layer, variant, model_key, item, rid, replicate, condition, renderer, tmpl, mock):
    return {"condition": condition, "layer": layer, "variant": variant, "item_id": item.item_id, "response_id": rid,
            "replicate": replicate, "template_name": tmpl, "template_sha256": renderer.template_sha(tmpl),
            "scorer_role": model_key, "mock": mock}


# ----------------------------------------------------------------------------- Katman 1
def build_layer1_jobs(responses: pd.DataFrame, bank: ItemBank, model_keys: list[str], variant: str,
                      replicate: int, renderer: PromptRenderer, condition: str = "") -> list[Job]:
    tmpl = TEMPLATES[("layer1", variant)]
    jobs = []
    for r in responses.itertuples(index=False):
        item = bank[r.item_id]
        anchors = item.anchors if variant == "anchored" else []
        system, user = renderer.render(tmpl, item=item, anchors=anchors, response_id=r.response_id,
                                       response_text=r.text)
        for mk in model_keys:
            mock = {"task": "layer1", "variant": variant, "item_id": item.item_id, "response_id": r.response_id,
                    "response_text": r.text, "criteria": _criteria_ranges(item),
                    "anchors": _anchor_dicts(item) if anchors else [], "reference": item.reference_answer}
            jobs.append(Job(LLMRequest(mk, system, [{"role": "user", "content": user}],
                                       _meta(1, variant, mk, item, r.response_id, replicate, condition, renderer,
                                             tmpl, mock)),
                            make_validator(item, r.response_id, ScoreOutput)))
    return jobs


# ----------------------------------------------------------------------------- Katman 2 / 3 yardımcıları
def _evaluations_by_response(rows: pd.DataFrame) -> dict[str, dict[str, list[dict]]]:
    """response_id -> model_key -> [ölçüt dict'leri]"""
    out: dict[str, dict[str, list[dict]]] = {}
    ok = rows[rows.error.isna() | (rows.error == "")]
    for (rid, mk), g in ok.groupby(["response_id", "model_key"]):
        out.setdefault(rid, {})[mk] = g.sort_values("criterion_id")[
            ["criterion_id", "score", "rationale", "rubric_evidence"]].to_dict("records")
    return out


def _shuffled_labels(model_keys: list[str], seed: int, rid: str, layer: int) -> list[tuple[str, str]]:
    rng = random.Random(f"{seed}|{rid}|{layer}")
    keys = list(model_keys)
    rng.shuffle(keys)
    return [(f"Model {string.ascii_uppercase[i]}", k) for i, k in enumerate(keys)]


def build_layer2_jobs(responses: pd.DataFrame, bank: ItemBank, l1_rows: pd.DataFrame, model_keys: list[str],
                      variant: str, replicate: int, renderer: PromptRenderer, order_seed: int,
                      include_anchors: bool = True, condition: str = "",
                      require_full_panel: bool = True) -> tuple[list[Job], list[str]]:
    """Her model kendi K1 puanını ve diğerlerininkini anonim (Model A/B/C), rastgele sırada görür."""
    tmpl = TEMPLATES[("layer2", variant)]
    evals = _evaluations_by_response(l1_rows)
    jobs, skipped = [], []
    for r in responses.itertuples(index=False):
        item = bank[r.item_id]
        ev = evals.get(r.response_id, {})
        avail = [k for k in model_keys if k in ev]
        anchors = item.anchors if (variant == "anchored" and include_anchors) else []
        min_n = len(model_keys) if require_full_panel else 2
        for mk in model_keys:
            if mk not in ev or len(avail) < min_n:
                skipped.append(f"{r.response_id}/{mk}")
                continue
            labels = _shuffled_labels(avail, order_seed, r.response_id, 2)
            own_label = next(lbl for lbl, k in labels if k == mk)
            evaluations = [{"label": lbl, "criteria": ev[k]} for lbl, k in labels]
            system, user = renderer.render(tmpl, item=item, anchors=anchors, response_id=r.response_id,
                                           response_text=r.text, evaluations=evaluations, own_label=own_label)
            mock = {"task": "layer2", "variant": variant, "item_id": item.item_id, "response_id": r.response_id,
                    "response_text": r.text, "criteria": _criteria_ranges(item),
                    "own": {c["criterion_id"]: c["score"] for c in ev[mk]},
                    "others": [{c["criterion_id"]: c["score"] for c in ev[k]} for k in avail if k != mk]}
            meta = _meta(2, variant, mk, item, r.response_id, replicate, condition, renderer, tmpl, mock)
            meta["label_order"] = {lbl: k for lbl, k in labels}
            jobs.append(Job(LLMRequest(mk, system, [{"role": "user", "content": user}], meta),
                            make_validator(item, r.response_id, RevisionOutput)))
    return jobs, skipped


def build_layer3_jobs(responses: pd.DataFrame, bank: ItemBank, l2_rows: pd.DataFrame, model_keys: list[str],
                      aggregator: str, variant: str, replicate: int, renderer: PromptRenderer, order_seed: int,
                      include_anchors: bool = True, condition: str = "",
                      require_full_panel: bool = True) -> tuple[list[Job], list[str]]:
    tmpl = TEMPLATES[("layer3", variant)]
    evals = _evaluations_by_response(l2_rows)
    jobs, skipped = [], []
    for r in responses.itertuples(index=False):
        item = bank[r.item_id]
        ev = evals.get(r.response_id, {})
        avail = [k for k in model_keys if k in ev]
        if len(avail) < (len(model_keys) if require_full_panel else 2):
            skipped.append(r.response_id)
            continue
        labels = _shuffled_labels(avail, order_seed, r.response_id, 3)
        anchors = item.anchors if (variant == "anchored" and include_anchors) else []
        system, user = renderer.render(tmpl, item=item, anchors=anchors, response_id=r.response_id,
                                       response_text=r.text,
                                       evaluations=[{"label": lbl, "criteria": ev[k]} for lbl, k in labels])
        mock = {"task": "layer3", "variant": variant, "item_id": item.item_id, "response_id": r.response_id,
                "response_text": r.text, "criteria": _criteria_ranges(item),
                "revised": [{c["criterion_id"]: c["score"] for c in ev[k]} for k in avail]}
        meta = _meta(3, variant, aggregator, item, r.response_id, replicate, condition, renderer, tmpl, mock)
        meta["label_order"] = {lbl: k for lbl, k in labels}
        jobs.append(Job(LLMRequest(aggregator, system, [{"role": "user", "content": user}], meta),
                        make_validator(item, r.response_id, ScoreOutput)))
    return jobs, skipped


# ----------------------------------------------------------------------------- sonuçlar -> satırlar
def outcomes_to_rows(outcomes: list[Outcome], run_id: str) -> pd.DataFrame:
    rows = []
    for o in outcomes:
        m = o.job.request.metadata
        base = {"run_id": run_id, "replicate": m["replicate"], "variant": m["variant"], "layer": m["layer"],
                "model_key": o.job.request.model_key, "item_id": m["item_id"], "response_id": m["response_id"]}
        if o.parsed is None:
            rows.append({**base, "criterion_id": None, "score": None, "call_id": o.call_ids[-1] if o.call_ids else None,
                         "error": o.error})
            continue
        for c in o.parsed["criteria"]:
            rows.append({**base, "criterion_id": c["criterion_id"], "score": c["score"], "rationale": c["rationale"],
                         "rubric_evidence": c.get("rubric_evidence", ""), "confidence": o.parsed["confidence"],
                         "changed": o.parsed.get("changed"), "total_mismatch": o.parsed.get("total_mismatch"),
                         "call_id": o.call_id, "error": None})
    return pd.DataFrame(rows, columns=ROW_COLUMNS)


@dataclass
class LayerPlan:
    """Bir çalıştırmada üretilecek LLM çağrı grupları."""
    layer1_anchored: bool = True
    layer1_zeroshot: bool = False
    layer2_anchored: bool = True
    layer2_zeroshot: bool = False
    layer3: bool = True
