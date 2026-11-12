"""Karşılaştırma koşulu: gömme tabanlı puanlama (üretken model yok).

Adımlar
  1. Her gömme modeli için öğrenci yanıtı ("query: ") ile o sorunun çapa ve referans yanıtları ("passage: ")
     arasındaki kosinüs benzerlikleri hesaplanır (E5 modelleri önek ister; diğerlerinde önek yok).
  2. Her model ve ölçüt için iki öznitelik: (a) referans yanıta benzerlik, (b) benzerlik-softmax ağırlıklı
     çapa puanı (o ölçütteki çapa puanlarının, benzerliğe göre ağırlıklı ortalaması).
  3. Öznitelikler model içinde standartlaştırılır (z; ortalama/SS yalnızca eğitim katından).
  4. Altın setin eğitim katlarında L2 düzenlileştirmeli sıralı lojistik regresyon (kümülatif logit) ile
     rubrik puanına çevrilir; yalnızca dışarıda tutulan kat tahmin edilir.

Yasak: yalnızca İngilizce modeller (all-mpnet, all-MiniLM) ve ince ayarsız ham BERT (yapılandırma da denetler).

Çevrimdışı demo: HuggingFace'e erişim yoksa `--offline-demo` ile karakter n-gram TF-IDF "kodlayıcı" kullanılır.
Bu YALNIZCA boru hattını sınamak içindir; koşul adı `embedding_tfidf_demo` olarak raporlanır.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from .config import ItemBank
from .utils import ensure_parent, sha256_text

FORBIDDEN_DEFAULT = ["all-mpnet", "all-MiniLM", "bert-base-uncased", "bert-base-cased", "bert-base-multilingual"]


# ----------------------------------------------------------------------------- kodlayıcılar
class SentenceTransformerEncoder:
    def __init__(self, name: str, query_prefix: str = "", passage_prefix: str = "", cache_dir: str | Path | None = None,
                 forbidden: list[str] | None = None):
        if any(b.lower() in name.lower() for b in (forbidden or FORBIDDEN_DEFAULT)):
            raise ValueError(f"Yasak gömme modeli: {name}")
        from sentence_transformers import SentenceTransformer  # isteğe bağlı bağımlılık: uv sync --extra embeddings
        self.name, self.qp, self.pp = name, query_prefix, passage_prefix
        self.model = SentenceTransformer(name, device="cpu")
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def encode(self, texts: list[str], kind: str) -> np.ndarray:
        prefix = self.qp if kind == "query" else self.pp
        cache = None
        if self.cache_dir:
            cache = ensure_parent(self.cache_dir / f"{self.name.replace('/', '__')}.npz")
        store = dict(np.load(cache)) if cache and cache.exists() else {}
        keys = [sha256_text(prefix + t) for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in store]
        if missing:
            emb = self.model.encode([prefix + texts[i] for i in missing], normalize_embeddings=True,
                                    batch_size=16, show_progress_bar=False)
            for i, e in zip(missing, emb):
                store[keys[i]] = e
            if cache:
                np.savez_compressed(cache, **store)
        return np.vstack([store[k] for k in keys])


class TfidfDemoEncoder:
    """Çevrimdışı DEMO kodlayıcı (karakter 3–5 gram TF-IDF). Bilimsel karşılaştırmada KULLANILMAZ."""

    def __init__(self, name: str = "offline-char-tfidf-demo", corpus: list[str] | None = None):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.name = name
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
        self.vec.fit(corpus or ["a"])

    def encode(self, texts: list[str], kind: str) -> np.ndarray:
        X = self.vec.transform(texts).toarray()
        n = np.linalg.norm(X, axis=1, keepdims=True)
        return X / np.where(n == 0, 1, n)


# ----------------------------------------------------------------------------- öznitelikler
def similarity_features(responses: pd.DataFrame, bank: ItemBank, encoders: list, temperature: float = 0.05) -> pd.DataFrame:
    """Uzun biçim: response_id, item_id, criterion_id, <enc>__sim_ref, <enc>__anchor_wscore"""
    rows = []
    for item_id, grp in responses.groupby("item_id"):
        item = bank[item_id]
        anchors = item.anchors
        ref = item.reference_answer or ""
        feats_per_enc = {}
        for enc in encoders:
            R = enc.encode(grp.text.tolist(), "query")
            A = enc.encode([a.text for a in anchors], "passage") if anchors else None
            F = enc.encode([ref], "passage")[0] if ref else None
            feats_per_enc[enc.name] = (R @ A.T if A is not None else None, R @ F if F is not None else None)
        for i, rid in enumerate(grp.response_id):
            for c in item.criteria:
                row = {"response_id": rid, "item_id": item_id, "criterion_id": c.criterion_id}
                for name, (SA, SF) in feats_per_enc.items():
                    row[f"{name}__sim_ref"] = float(SF[i]) if SF is not None else np.nan
                    if SA is not None:
                        s = SA[i] / temperature
                        w = np.exp(s - s.max())
                        w /= w.sum()
                        row[f"{name}__anchor_wscore"] = float(np.dot(w, [a.scores[c.criterion_id] for a in anchors]))
                    else:
                        row[f"{name}__anchor_wscore"] = np.nan
                rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- sıralı lojistik
@dataclass
class OrdinalLogistic:
    """Kümülatif logit (proportional odds): P(y ≤ k | x) = σ(θ_k − xβ), L2 cezalı β.

    Eşikler θ_0 + Σ exp(δ) ile sıralı tutulur; eğitimde görülmeyen düzeyler de modellenir.
    """
    lo: int
    hi: int
    l2: float = 1.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "OrdinalLogistic":
        X, y = np.asarray(X, float), np.asarray(y, int) - self.lo
        n, p = X.shape
        K = self.hi - self.lo + 1

        def unpack(par):
            beta = par[:p]
            th = np.concatenate([[par[p]], par[p] + np.cumsum(np.exp(par[p + 1:]))])
            return beta, th

        def nll(par):
            beta, th = unpack(par)
            eta = X @ beta
            cdf = np.column_stack([np.zeros(n), expit(th[None, :] - eta[:, None]), np.ones(n)])
            pr = cdf[np.arange(n), y + 1] - cdf[np.arange(n), y]
            return -np.sum(np.log(np.clip(pr, 1e-12, None))) + self.l2 * np.sum(beta ** 2)

        init = np.concatenate([np.zeros(p), [-(K - 2) / 2], np.zeros(K - 2)])
        res = minimize(nll, init, method="L-BFGS-B")
        self.beta_, self.theta_ = unpack(res.x)
        self.converged_ = bool(res.success)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        eta = np.asarray(X, float) @ self.beta_
        n = len(eta)
        cdf = np.column_stack([np.zeros(n), expit(self.theta_[None, :] - eta[:, None]), np.ones(n)])
        return np.diff(cdf, axis=1)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1) + self.lo


def cv_embedding_scores(feats: pd.DataFrame, y: pd.DataFrame, folds: pd.DataFrame, ranges: pd.DataFrame,
                        level: str = "item", l2: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kat dışı tahminler. y: response_id, criterion_id, y; ranges: item_id, criterion_id, score_min, score_max"""
    df = (feats.merge(y, on=["response_id", "criterion_id"]).merge(folds[["response_id", "fold"]], on="response_id")
          .merge(ranges, on=["item_id", "criterion_id"]))
    fcols = [c for c in feats.columns if "__" in c and feats[c].notna().any()]
    df["group"] = {"item": df.item_id, "item_criterion": df.item_id + "/" + df.criterion_id,
                   "global": pd.Series("all", index=df.index)}[level]
    df["pred"] = np.nan
    coefs = []
    for k in sorted(df.fold.unique()):
        for g in df.group.unique():
            tr = (df.fold != k) & (df.group == g)
            te = (df.fold == k) & (df.group == g)
            if te.sum() == 0 or tr.sum() < 5:
                continue
            Xtr, Xte = df.loc[tr, fcols].to_numpy(float), df.loc[te, fcols].to_numpy(float)
            mu, sd = np.nanmean(Xtr, axis=0), np.nanstd(Xtr, axis=0)
            sd[sd == 0] = 1
            Xtr, Xte = np.nan_to_num((Xtr - mu) / sd), np.nan_to_num((Xte - mu) / sd)
            lo, hi = int(df.loc[tr, "score_min"].min()), int(df.loc[tr, "score_max"].max())
            m = OrdinalLogistic(lo, hi, l2).fit(Xtr, df.loc[tr, "y"].to_numpy())
            df.loc[te, "pred"] = m.predict(Xte)
            coefs += [{"fold": int(k), "group": g, "feature": f, "coef": float(b)} for f, b in zip(fcols, m.beta_)]
    return df[["response_id", "item_id", "criterion_id", "pred"] + fcols], pd.DataFrame(coefs)


def log_embedding_run(run_id: str, logs_dir: str | Path, preds: pd.DataFrame, encoder_names: list[str],
                      condition: str) -> pd.DataFrame:
    """Her gömme tahmini de çağrı kaydına yazılır (kural: kaydı olmayan sonuç raporlanmaz)."""
    path = ensure_parent(Path(logs_dir) / run_id / "calls.jsonl")
    preds = preds.copy()
    preds["call_id"] = [uuid.uuid4().hex for _ in range(len(preds))]
    fcols = [c for c in preds.columns if "__" in c]
    with open(path, "a", encoding="utf-8") as f:
        for d in preds.to_dict("records"):
            f.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "run_id": run_id,
                                "call_id": d["call_id"], "call_type": "embedding", "condition": condition,
                                "layer": None, "model_key": "embedding", "model_requested": encoder_names,
                                "item_id": d["item_id"], "response_id": d["response_id"],
                                "criterion_id": d["criterion_id"],
                                "features": {c: d[c] for c in fcols if c in d},
                                "parsed_output": {"score": None if pd.isna(d["pred"]) else int(d["pred"])},
                                "error": None}, ensure_ascii=False, default=float) + "\n")
    return preds
