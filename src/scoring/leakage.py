"""Altın set sızıntı denetimi.

Modellere verilen çapa yanıtlar (ve gömme koşulunda kullanılan çapa/referans yanıtlar) değerlendirme
için kullanılan altın setten ASLA gelemez. İki düzeyde denetlenir:
  1. Kimlik: çapanın source_response_id'si altın sette mi?
  2. İçerik: çapa metninin normalleştirilmiş SHA-256 özeti herhangi bir altın set yanıtınınkiyle aynı mı?
     (Ayrıca çok yüksek sözcük örtüşmesi — Jaccard ≥ eşik — yakın kopya olarak yakalanır.)
"""
from __future__ import annotations

import pandas as pd

from .config import ItemBank
from .utils import normalize_for_hash, text_fingerprint


class LeakageError(RuntimeError):
    pass


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(normalize_for_hash(a).split()), set(normalize_for_hash(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def check_leakage(bank: ItemBank, responses: pd.DataFrame, gold_ids: set[str],
                  near_dup_threshold: float = 0.9) -> list[str]:
    """İhlal varsa LeakageError fırlatır; yoksa yapılan denetimlerin özetini döndürür."""
    gold = responses[responses.response_id.isin(gold_ids)]
    gold_fp = {text_fingerprint(t): rid for rid, t in zip(gold.response_id, gold.text) if t.strip()}
    violations, notes = [], []
    for it in bank.items:
        gold_item = gold[gold.item_id == it.item_id]
        for a in it.anchors:
            if a.source_response_id and a.source_response_id in gold_ids:
                violations.append(f"{a.anchor_id}: kaynak yanıt {a.source_response_id} altın sette")
            fp = text_fingerprint(a.text)
            if fp in gold_fp:
                violations.append(f"{a.anchor_id}: metni altın set yanıtı {gold_fp[fp]} ile özdeş")
            for rid, t in zip(gold_item.response_id, gold_item.text):
                if _jaccard(a.text, t) >= near_dup_threshold:
                    violations.append(f"{a.anchor_id}: altın set yanıtı {rid} ile yakın kopya (Jaccard≥{near_dup_threshold})")
        notes.append(f"{it.item_id}: {len(it.anchors)} çapa, {len(gold_item)} altın set yanıtına karşı denetlendi")
    if violations:
        raise LeakageError("ALTIN SET SIZINTISI:\n  " + "\n  ".join(violations))
    return notes
