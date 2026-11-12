"""Ortak yardımcılar: özetler, Türkçe küçük harf, yuvarlama, dosya G/Ç."""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def tr_lower(text: str) -> str:
    """Türkçe'ye duyarlı küçük harf (İ->i, I->ı)."""
    return text.replace("İ", "i").replace("I", "ı").lower()


_FOLD = str.maketrans("ıiİşğçöüâîû", "iiisgcouaiu")


def normalize_for_hash(text: str) -> str:
    """Sızıntı denetimi için metin normalleştirme: NFC, Türkçe küçük harf, aksan katlama (ı/i, ş/s ...),
    noktalama ve fazla boşluk silinir. Büyük/küçük harf ve Türkçe karakter farkları yakalanır."""
    t = unicodedata.normalize("NFC", text or "")
    t = tr_lower(t).translate(_FOLD)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def text_fingerprint(text: str) -> str:
    return sha256_text(normalize_for_hash(text))


def round_score(x: float, rule: str = "half_up") -> int:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        raise ValueError("NaN puan yuvarlanamaz")
    mode = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN}[rule]
    return int(Decimal(str(float(x))).quantize(Decimal("1"), rounding=mode))


def round_clip(values: Iterable[float], lo: int, hi: int, rule: str = "half_up") -> np.ndarray:
    return np.array([min(hi, max(lo, round_score(v, rule))) for v in values], dtype=int)


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_table(df, stem: str | Path, floatfmt: str = ".3f") -> None:
    """Tabloyu hem CSV hem Markdown olarak yazar."""
    stem = Path(stem)
    ensure_parent(stem)
    df.to_csv(stem.with_suffix(".csv"), index=False)
    stem.with_suffix(".md").write_text(df_to_markdown(df, floatfmt), encoding="utf-8")


def df_to_markdown(df, floatfmt: str = ".3f") -> str:
    def fmt(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else format(float(v), floatfmt)
        return str(v)

    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines) + "\n"
