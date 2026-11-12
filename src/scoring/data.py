"""Anonim yanıtlar ve insan puanlarının yüklenmesi; altın set uzlaşı puanı."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import ItemBank
from .utils import round_score

HUMAN_COLUMNS = ["response_id", "rater_id", "role", "set", "criterion_id", "score"]
FORBIDDEN_RESPONSE_COLUMNS = {"first_name", "last_name", "email", "id_number", "username", "adı", "soyadı",
                              "e-posta adresi", "kullanıcı adı", "id numarası"}


def load_responses(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"response_id": str, "student_code": str, "item_id": str})
    bad = {c.lower() for c in df.columns} & FORBIDDEN_RESPONSE_COLUMNS
    if bad:
        raise RuntimeError(f"Yanıt dosyasında kimlik sütunu var: {bad}. Önce `scoring anonymize` çalıştırın.")
    df["text"] = df["text"].fillna("")
    return df


def load_human_scores(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"response_id": str, "rater_id": str, "criterion_id": str})
    missing = set(HUMAN_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"human_scores.csv eksik sütunlar: {missing}")
    return df


def official_scores(human: pd.DataFrame) -> pd.DataFrame:
    """response_id × criterion_id resmî puanlar (tek puanlayıcı)."""
    return human[human.set == "official"][["response_id", "criterion_id", "score"]]


def gold_consensus(human: pd.DataFrame, rule: str = "adjudicator_or_mean", rounding: str = "half_up") -> pd.DataFrame:
    """Altın set için uzlaşı puanı ve iki puanlayıcının puanları (geniş biçim).

    Sütunlar: response_id, criterion_id, rater1, rater2, adjudicator, consensus
    """
    g = human[human.set == "gold"]
    wide = g.pivot_table(index=["response_id", "criterion_id"], columns="role", values="score", aggfunc="first")
    for c in ("rater1", "rater2", "adjudicator"):
        if c not in wide:
            wide[c] = np.nan
    wide = wide.reset_index()
    if wide[["rater1", "rater2"]].isna().any().any():
        n = int(wide[["rater1", "rater2"]].isna().any(axis=1).sum())
        raise ValueError(f"Altın sette {n} satırda iki puanlayıcıdan biri eksik.")

    def cons(row):
        if row.rater1 == row.rater2:
            return int(row.rater1)
        if rule == "adjudicator_or_mean" and not np.isnan(row.adjudicator):
            return int(row.adjudicator)
        return round_score((row.rater1 + row.rater2) / 2, rounding)

    wide["consensus"] = wide.apply(cons, axis=1).astype(int)
    return wide[["response_id", "criterion_id", "rater1", "rater2", "adjudicator", "consensus"]]


def totals(df: pd.DataFrame, value_cols: list[str], key: str = "response_id") -> pd.DataFrame:
    """Ölçüt puanlarından toplam puan (ölçüt toplamı)."""
    return df.groupby(key)[value_cols].sum(min_count=1).reset_index()


def criteria_frame(bank: ItemBank) -> pd.DataFrame:
    return pd.DataFrame([{"item_id": it.item_id, "criterion_id": c.criterion_id, "score_min": c.score_min,
                          "score_max": c.score_max, "bloom": it.bloom}
                         for it in bank.items for c in it.criteria])
