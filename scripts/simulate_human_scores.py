"""SENTETİK insan puanları üretir (yalnızca geliştirme). Gerçek çalışmada data/human_scores.csv
puanlayıcıların doldurduğu dosyalardan oluşturulur.

  --stage official : tüm yanıtlar için tek puanlayıcılı resmî not (gerçek puan + gürültü)
  --stage gold     : altın setteki yanıtlar için iki kör puanlayıcı + farklılıklarda hakem

Gizli gerçek puanlara ulaşmak için şifreli eşleme tablosu çözülür (kod -> e-posta), böylece
puanlayıcı simülasyonu anonim yanıt kodlarıyla eşleştirilir.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from scoring.anonymize import load_mapping
from scoring.config import load_experiment

COLUMNS = ["response_id", "rater_id", "role", "set", "criterion_id", "score"]


def noisy(true: np.ndarray, rng, p1: float, p2: float, lo=0, hi=4) -> np.ndarray:
    u = rng.random(len(true))
    step = np.where(u < p2, 2, np.where(u < p2 + p1, 1, 0)) * rng.choice([-1, 1], len(true))
    return np.clip(true + step, lo, hi)


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["official", "gold"], required=True)
    ap.add_argument("--truth", default="data/synthetic/latent_truth.csv")
    ap.add_argument("--seed", type=int, default=31)
    args = ap.parse_args()
    exp = load_experiment()
    rng = np.random.default_rng(args.seed + (0 if args.stage == "official" else 1))

    mapping = load_mapping(exp.path("mapping"))
    code_to_email = {v["code"]: v["identity"]["email"] for v in mapping["students"].values()}
    rid_rows = [{"response_id": rid, "email": code_to_email[k.split("|")[0]], "item_id": k.split("|")[1]}
                for k, rid in mapping["responses"].items()]
    truth = pd.read_csv(args.truth).merge(pd.DataFrame(rid_rows), on=["email", "item_id"])
    responses = pd.read_csv(exp.path("responses"))
    truth = truth[truth.response_id.isin(responses.loc[~responses.is_empty, "response_id"])]

    out_path = exp.path("human_scores")
    existing = pd.read_csv(out_path) if out_path.exists() else pd.DataFrame(columns=COLUMNS)

    if args.stage == "official":
        t = truth.copy()
        t["score"] = noisy(t.true_score.to_numpy(), rng, p1=0.28, p2=0.03)
        new = t.assign(rater_id="H_OFF", role="official", set="official")[COLUMNS]
        existing = existing[existing.set != "official"]
    else:
        gold = pd.read_csv(exp.path("gold_sample"))
        t = truth[truth.response_id.isin(gold.response_id)].copy()
        r1 = noisy(t.true_score.to_numpy(), rng, p1=0.22, p2=0.02)
        r2 = noisy(t.true_score.to_numpy(), rng, p1=0.22, p2=0.02)
        adj = noisy(t.true_score.to_numpy(), rng, p1=0.10, p2=0.0)
        parts = [t.assign(rater_id="H_A", role="rater1", set="gold", score=r1),
                 t.assign(rater_id="H_B", role="rater2", set="gold", score=r2)]
        dis = r1 != r2
        parts.append(t[dis].assign(rater_id="H_ADJ", role="adjudicator", set="gold", score=adj[dis]))
        new = pd.concat(parts)[COLUMNS]
        existing = existing[existing.set != "gold"]
    out = pd.concat([existing, new]).sort_values(["set", "response_id", "role", "criterion_id"])
    out["score"] = out["score"].astype(int)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"{args.stage}: {len(new)} puan satırı yazıldı -> {out_path}")


if __name__ == "__main__":
    main()
