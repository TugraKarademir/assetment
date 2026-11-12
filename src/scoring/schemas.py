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


def json_schema_for(item: Item, response_id: str, revision: bool = False) -> dict:
    """Kısıtlı çözümleme (llama.cpp / vLLM / Ollama) için JSON şeması: ölçüt kimlikleri sabit sırada, puanlar o
    ölçütün aralığında tamsayı. Model yapısal olarak geçersiz çıktı üretemez; pydantic doğrulaması yine çalışır."""
    crit = [{"type": "object",
             "properties": {"criterion_id": {"type": "string", "enum": [c.criterion_id]},
                            "score": {"type": "integer", "minimum": c.score_min, "maximum": c.score_max},
                            "rationale": {"type": "string"},
                            "rubric_evidence": {"type": "string"}},
             "required": ["criterion_id", "score", "rationale", "rubric_evidence"],
             "additionalProperties": False} for c in item.criteria]
    props = {"item_id": {"type": "string", "enum": [item.item_id]},
             "response_id": {"type": "string", "enum": [response_id]},
             "criteria": {"type": "array", "prefixItems": crit,
                          "minItems": len(crit), "maxItems": len(crit)},
             "total": {"type": "integer", "minimum": item.total_min, "maximum": item.total_max},
             "confidence": {"type": "number", "minimum": 0, "maximum": 1}}
    if revision:
        props["changed"] = {"type": "boolean"}
        props["revision_reason"] = {"type": "string"}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def evidence_in_response(evidence: str, response_text: str) -> bool | None:
    """Kanıt alıntısı yanıtta birebir geçiyor mu? (büyük/küçük harf, noktalama ve Türkçe karakter farkı yok sayılır)
    Boş alıntı -> None. Kalite göstergesidir; puanı reddetmez."""
    from .utils import normalize_for_hash
    ev = normalize_for_hash(evidence or "")
    if not ev:
        return None
    return ev in normalize_for_hash(response_text or "")


def make_validator(item: Item, response_id: str, schema: type[ScoreOutput] = ScoreOutput,
                   response_text: str | None = None):
    """Rubriğe göre doğrulama: şema, kimlikler, ölçüt kümesi, puan aralığı. Toplam uyuşmazlığı not edilir.
    response_text verilirse her ölçüt için kanıt alıntısının yanıtta birebir geçip geçmediği işaretlenir."""

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
        if response_text is not None:
            for c in out["criteria"]:
                c["evidence_verbatim"] = evidence_in_response(c.get("rubric_evidence", ""), response_text)
        s = sum(c.score for c in obj.criteria)
        out["total_reported"] = obj.total
        out["total_mismatch"] = obj.total is not None and abs(obj.total - s) > 1e-9
        out["total"] = s
        return out, None

    return validate
