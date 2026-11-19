"""Yapılandırma dosyalarının pydantic modelleri ve yükleyicileri."""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .utils import sha256_file

CONFIG_DIR = Path("config")


# ----------------------------------------------------------------------------- items / rubrik
class Criterion(BaseModel):
    criterion_id: str
    name: str
    description: str = ""
    score_min: int = 0
    score_max: int = 4
    levels: dict[int, str]

    @model_validator(mode="after")
    def _levels_cover_range(self):
        expected = set(range(self.score_min, self.score_max + 1))
        if set(self.levels) != expected:
            raise ValueError(f"{self.criterion_id}: her puan düzeyi için tanımlayıcı gerekli {sorted(expected)}, "
                             f"bulunan {sorted(self.levels)}")
        return self


class Anchor(BaseModel):
    anchor_id: str
    text: str
    scores: dict[str, int]
    source: str = ""
    source_response_id: str | None = None


class Item(BaseModel):
    item_id: str
    bloom: Literal["alt", "üst"]
    bloom_level: str = ""
    question: str
    reference_answer: str | None = None
    criteria: list[Criterion]
    anchors: list[Anchor] = Field(default_factory=list)

    @property
    def criterion_ids(self) -> list[str]:
        return [c.criterion_id for c in self.criteria]

    def criterion(self, cid: str) -> Criterion:
        for c in self.criteria:
            if c.criterion_id == cid:
                return c
        raise KeyError(cid)

    @property
    def total_max(self) -> int:
        return sum(c.score_max for c in self.criteria)

    @property
    def total_min(self) -> int:
        return sum(c.score_min for c in self.criteria)

    @model_validator(mode="after")
    def _check_anchors(self):
        cids = set(self.criterion_ids)
        for a in self.anchors:
            if set(a.scores) != cids:
                raise ValueError(f"{a.anchor_id}: çapa puanları tüm ölçütleri kapsamalı {sorted(cids)}")
            for cid, s in a.scores.items():
                c = self.criterion(cid)
                if not c.score_min <= s <= c.score_max:
                    raise ValueError(f"{a.anchor_id}/{cid}: çapa puanı aralık dışında")
        # Her ölçütün her düzeyi için en az bir çapa (uyarı yerine hata: belge bunu istiyor)
        for c in self.criteria:
            covered = {a.scores[c.criterion_id] for a in self.anchors}
            missing = set(range(c.score_min, c.score_max + 1)) - covered
            if self.anchors and missing:
                raise ValueError(f"{self.item_id}/{c.criterion_id}: şu puan düzeyleri için çapa yok: {sorted(missing)}")
        return self


class ItemBank(BaseModel):
    items: list[Item]

    def __getitem__(self, item_id: str) -> Item:
        for it in self.items:
            if it.item_id == item_id:
                return it
        raise KeyError(item_id)

    @property
    def ids(self) -> list[str]:
        return [i.item_id for i in self.items]


def items_path() -> Path:
    """Kullanılacak soru/rubrik dosyası: SCORING_ITEMS ortam değişkeni > experiment.yaml:items_file > config/items.yaml"""
    import os
    if os.environ.get("SCORING_ITEMS"):
        return Path(os.environ["SCORING_ITEMS"])
    exp = CONFIG_DIR / "experiment.yaml"
    if exp.exists():
        f = (yaml.safe_load(exp.read_text(encoding="utf-8")) or {}).get("items_file")
        if f:
            return Path(f)
    return CONFIG_DIR / "items.yaml"


def load_items(path: str | Path | None = None) -> ItemBank:
    path = Path(path) if path else items_path()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    d = raw.get("defaults", {})
    for it in raw["items"]:
        for c in it["criteria"]:
            c.setdefault("score_min", d.get("score_min", 0))
            c.setdefault("score_max", d.get("score_max", 4))
    return ItemBank(items=raw["items"])


# ----------------------------------------------------------------------------- modeller
class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    key: str = ""
    provider: Literal["openai", "anthropic", "google", "openai_compat", "mock"]
    model: str
    family: str = ""
    open_weights: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    batch: bool = False
    max_concurrency: int = 4
    base_url_env: str | None = None
    price_input_per_mtok: float = 0.0
    price_output_per_mtok: float = 0.0


class RetrySpec(BaseModel):
    max_validation_retries: int = 2
    max_api_retries: int = 6
    backoff_initial_seconds: float = 2
    backoff_max_seconds: float = 120


class ModelsConfig(BaseModel):
    scorers: list[str]
    aggregator: str
    models: dict[str, ModelSpec]
    retry: RetrySpec = RetrySpec()
    source_path: str = ""

    @model_validator(mode="after")
    def _check(self):
        for k, m in self.models.items():
            m.key = k
        for k in [*self.scorers, self.aggregator]:
            if k not in self.models:
                raise ValueError(f"models.yaml: '{k}' tanımlı değil")
        if len(self.scorers) < 2:
            raise ValueError("En az iki puanlayıcı model gerekli")
        if not any(self.models[k].open_weights for k in [*self.scorers, self.aggregator]):
            raise ValueError("Panelde en az bir açık ağırlıklı (open_weights: true) model bulunmalıdır")
        return self

    def spec(self, key: str) -> ModelSpec:
        return self.models[key]


def load_models(path: str | Path = CONFIG_DIR / "models.yaml") -> ModelsConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ModelsConfig(**raw, source_path=str(path))


# ----------------------------------------------------------------------------- deney
class Experiment(BaseModel):
    model_config = ConfigDict(extra="allow")
    seeds: dict[str, int]
    paths: dict[str, str]
    gold: dict[str, Any]
    aggregation: dict[str, Any]
    embedding: dict[str, Any]
    evaluation: dict[str, Any]
    cost: dict[str, Any]
    prompt: dict[str, Any] = Field(default_factory=dict)

    @property
    def prompt_options(self) -> dict[str, Any]:
        return self.prompt or {}

    def path(self, key: str) -> Path:
        p = Path(self.paths[key])
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @field_validator("embedding")
    @classmethod
    def _no_forbidden_embeddings(cls, v):
        bad = v.get("forbidden_patterns", [])
        for m in v.get("models", []):
            if any(b.lower() in m["name"].lower() for b in bad):
                raise ValueError(f"Gömme modeli yasak listesinde: {m['name']} (yalnızca İngilizce/ham BERT kullanılamaz)")
        return v


def load_experiment(path: str | Path = CONFIG_DIR / "experiment.yaml") -> Experiment:
    return Experiment(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def config_hashes(paths: list[str | Path]) -> dict[str, str]:
    return {str(p): sha256_file(p) for p in paths if Path(p).exists()}
