"""Gizli işaret ("kanarya") denetimi: soru metnine öğrencilerin görmediği bir talimat eklenir. Soru bir yapay zekâya
kopyalanırsa talimat da gider ve YZ cevabı normalde kimsenin yazmayacağı bir iz (ör. uydurma bir kavram adı)
taşır. Bu modül yanıtlarda o izleri arar.

- İşaretler config/canary.local.yaml dosyasında tutulur. Dosya .gitignore kapsamındadır: işaretler depoda
  (GitHub) görünürse öğrenciler bulabilir. Örnek biçim: config/canary.example.yaml
- Eşleştirme büyük/küçük harf, Türkçe karakter (ı/i, ş/s ...), noktalama ve tire farkına duyarsızdır.
- Bir eşleşme KANIT DEĞİL, işarettir; yorum ve olası işlem kurumun akademik dürüstlük sürecine göre yapılır.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .utils import normalize_for_hash

DEFAULT_PATH = Path("config/canary.local.yaml")


def load_canaries(path: str | Path = DEFAULT_PATH) -> dict[str, list[str]]:
    """{item_id: [işaret ifadeleri]} — dosya yoksa boş sözlük."""
    p = Path(path)
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[str, list[str]] = {}
    for item_id, spec in (raw.get("items") or {}).items():
        terms = spec.get("detect", []) if isinstance(spec, dict) else spec
        out[str(item_id)] = [str(t) for t in terms if str(t).strip()]
    return out


def find_markers(text: str, terms: list[str]) -> list[str]:
    hay = f" {normalize_for_hash(text)} "
    return [t for t in terms if f" {normalize_for_hash(t)} " in hay]


def flag_responses(responses: pd.DataFrame, canaries: dict[str, list[str]]) -> pd.DataFrame:
    """response_id, item_id, canary_hit (bool), canary_terms (eşleşen ifadeler; ';' ile)."""
    rows = []
    for r in responses.itertuples(index=False):
        hits = find_markers(r.text, canaries.get(r.item_id, []))
        rows.append({"response_id": r.response_id, "item_id": r.item_id, "canary_hit": bool(hits),
                     "canary_terms": ";".join(hits)})
    return pd.DataFrame(rows, columns=["response_id", "item_id", "canary_hit", "canary_terms"])


def summary(flags: pd.DataFrame) -> pd.DataFrame:
    """Soru başına sayımlar (yanıt kodu içermez; paylaşılabilir)."""
    if flags.empty:
        return pd.DataFrame(columns=["item_id", "n_responses", "n_flagged", "pct_flagged"])
    g = flags.groupby("item_id").canary_hit.agg(n_responses="size", n_flagged="sum").reset_index()
    g["pct_flagged"] = (100 * g.n_flagged / g.n_responses).round(1)
    return g
