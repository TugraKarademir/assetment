"""Yanlılık analizi için metin öznitelikleri: uzunluk, yazım hatası sayısı, sözcük çeşitliliği.

Yazım hatası yöntemi (README'de belgelenmiştir):
  - Sözlük: Türkçe Hunspell (wooorm/dictionaries `tr`, MIT), saf-Python `spylls` ile morfolojik denetim
    (Türkçe eklemeli yapısı nedeniyle düz sözcük listesi yerine Hunspell ek kuralları kullanılır).
  - Belirteçler: yalnızca harflerden oluşan, en az 3 karakterli sözcükler; anonimleştirme maskeleri ([AD] vb.),
    sayılar ve config/spelling_whitelist.txt içindeki alan terimleri hariç.
  - Bir sözcük; özgün haliyle, Türkçe küçük harfle ya da şapkasız (â->a) haliyle sözlükte yoksa hata sayılır.
  - Sözlük bulunamazsa sütun boş (NA) bırakılır ve yöntem "unavailable" olarak kaydedilir.
Sözcük çeşitliliği: MTLD (McCarthy & Jarvis, 2010; eşik .72, iki yönlü ortalama; ≥100 sözcükte güvenilir),
MATTR (pencere 25; kısa yanıtlar için önerilen) ve TTR.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import tr_lower

TOKEN_RE = re.compile(r"[A-Za-zÇĞİÖŞÜÂÎÛçğıöşüâîû]+")
MASK_RE = re.compile(r"\[[A-ZÇĞİÖŞÜ]+\]")


def tokens(text: str) -> list[str]:
    return [tr_lower(t) for t in TOKEN_RE.findall(MASK_RE.sub(" ", text or ""))]


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", MASK_RE.sub(" ", text or "")))


def ttr(toks: list[str]) -> float:
    return len(set(toks)) / len(toks) if toks else np.nan


def _mtld_pass(toks: list[str], threshold: float) -> float:
    factors, types, count = 0.0, set(), 0
    for t in toks:
        count += 1
        types.add(t)
        if len(types) / count <= threshold:
            factors += 1
            types, count = set(), 0
    if count:
        cur = len(types) / count
        factors += (1 - cur) / (1 - threshold) if cur < 1 else 0
    return len(toks) / factors if factors else np.nan


def mtld(toks: list[str], threshold: float = 0.72) -> float:
    if len(toks) < 10:
        return np.nan
    vals = [v for v in (_mtld_pass(toks, threshold), _mtld_pass(toks[::-1], threshold)) if not np.isnan(v)]
    return float(np.mean(vals)) if vals else np.nan


def mattr(toks: list[str], window: int = 25) -> float:
    """Hareketli ortalamalı TTR (Covington & McFall, 2010); kısa metinlerde MTLD'den kararlıdır."""
    if not toks:
        return np.nan
    if len(toks) <= window:
        return ttr(toks)
    from collections import Counter
    c = Counter(toks[:window])
    vals = [len(c) / window]
    for i in range(window, len(toks)):
        out = toks[i - window]
        c[out] -= 1
        if c[out] == 0:
            del c[out]
        c[toks[i]] += 1
        vals.append(len(c) / window)
    return float(np.mean(vals))


class SpellChecker:
    def __init__(self, dict_prefix: str | Path = "data/resources/hunspell_tr/index",
                 whitelist: str | Path = "config/spelling_whitelist.txt"):
        self.method = "unavailable"
        self.dic = None
        self.whitelist = set()
        wl = Path(whitelist)
        if wl.exists():
            self.whitelist = {tr_lower(x.strip()) for x in wl.read_text(encoding="utf-8").splitlines()
                              if x.strip() and not x.startswith("#")}
        if Path(str(dict_prefix) + ".dic").exists():
            try:
                from spylls.hunspell import Dictionary
                self.dic = Dictionary.from_files(str(dict_prefix))
                self.method = "hunspell-tr (spylls) + alan terimi beyaz listesi"
            except ImportError:
                self.method = "unavailable (spylls kurulu değil: uv sync --extra spelling)"

    @lru_cache(maxsize=200_000)
    def is_error(self, word: str) -> bool:
        if len(word) < 3 or word in self.whitelist:
            return False
        for w in (word, tr_lower(word), word.translate(str.maketrans("âîû", "aiu"))):
            if self.dic.lookup(w):
                return False
        return True

    def count(self, text: str) -> float:
        if self.dic is None:
            return np.nan
        return float(sum(self.is_error(t) for t in TOKEN_RE.findall(MASK_RE.sub(" ", text or ""))))


def text_features(responses: pd.DataFrame, checker: SpellChecker | None = None) -> pd.DataFrame:
    checker = checker or SpellChecker()
    rows = []
    for r in responses.itertuples(index=False):
        toks = tokens(r.text)
        rows.append({"response_id": r.response_id, "n_words": word_count(r.text),
                     "n_spelling_errors": checker.count(r.text),
                     "spelling_error_rate": (checker.count(r.text) / len(toks)) if toks and checker.dic else np.nan,
                     "mtld": mtld(toks), "mattr": mattr(toks), "ttr": ttr(toks)})
    out = pd.DataFrame(rows)
    out.attrs["spelling_method"] = checker.method
    return out
