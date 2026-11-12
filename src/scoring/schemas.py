"""LLM çıktı şemaları (pydantic) ve rubriğe bağlı doğrulayıcılar."""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import Item


class CriterionScore(BaseModel):
    criterion_id: str
    score: int
    rationale: str
    rubric_evidence: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _strict_integer(cls, v):
        if isinstance(v, bool):
            raise ValueError("puan tamsayı olmalı")
        if isinstance(v, float) and not v.is_integer():
            raise ValueError(f"puan tamsayı olmalı (gelen {v})")
        return v


class ScoreOutput(BaseModel):
    item_id: str
    response_id: str
    criteria: list[CriterionScore]
    total: float | None = None
    confidence: float = Field(ge=0, le=1)


class RevisionOutput(ScoreOutput):
    changed: bool
    revision_reason: str


def extract_json(text: str) -> dict:
    """Model çıktısından JSON nesnesini çıkarır (```json çitleri ve önündeki/arkasındaki metin temizlenir)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        if s == -1 or e <= s:
            raise ValueError("çıktıda JSON nesnesi bulunamadı")
        return json.loads(t[s:e + 1])


def make_validator(item: Item, response_id: str, schema: type[ScoreOutput] = ScoreOutput):
    """Rubriğe göre doğrulama: şema, kimlikler, ölçüt kümesi, puan aralığı. Toplam uyuşmazlığı not edilir."""

    def validate(text: str) -> tuple[dict[str, Any] | None, str | None]:
        try:
            obj = schema.model_validate(extract_json(text))
        except (ValueError, ValidationError) as e:
            return None, f"şema/JSON hatası: {str(e)[:500]}"
        if obj.item_id != item.item_id or obj.response_id != response_id:
            return None, f"kimlik uyuşmazlığı: beklenen {item.item_id}/{response_id}, gelen {obj.item_id}/{obj.response_id}"
        got = [c.criterion_id for c in obj.criteria]
        if sorted(got) != sorted(item.criterion_ids) or len(set(got)) != len(got):
            return None, f"ölçüt kümesi hatalı: beklenen {item.criterion_ids}, gelen {got}"
        for c in obj.criteria:
            crit = item.criterion(c.criterion_id)
            if not crit.score_min <= c.score <= crit.score_max:
                return None, f"{c.criterion_id} puanı aralık dışında: {c.score} ∉ [{crit.score_min}, {crit.score_max}]"
        out = obj.model_dump()
        s = sum(c.score for c in obj.criteria)
        out["total_reported"] = obj.total
        out["total_mismatch"] = obj.total is not None and abs(obj.total - s) > 1e-9
        out["total"] = s
        return out, None

    return validate
