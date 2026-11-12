"""Sentetik Moodle dışa aktarımı üretir (etik kurul onayı öncesi geliştirme için).

Çıktılar:
  data/raw/moodle_export.csv        Moodle "Yanıtlar" raporu biçiminde (Türkçe başlıklar), kimlik sütunları dahil
  data/synthetic/latent_truth.csv   Her (e-posta, soru, ölçüt) için gizli "gerçek" puan — yalnızca insan
                                    puanlayıcıları simüle etmek için kullanılır, modellere asla verilmez.

Tasarım:
  - Öğrenci yeteneği θ ~ N(0, 1); ölçüt puanı = yuvarla(2 + 1.1·θ + soru güçlüğü + N(0, 0.7)), [0, 4]'e kırpılır.
  - Metin, her ölçüt için o düzeye ait cümle bankasından kurulur; düşük kalitede yazım hataları ve konu dışı
    cümleler daha olasıdır; uzunluk kaliteyle kısmen ilişkilidir (gerçekçi uzunluk yanlılığı denetimi için).
  - Yanıtların ~%8'ine maskeleme filtresini sınamak için ad, numara, e-posta ya da telefon eklenir.

Kullanım:  uv run python scripts/make_synthetic.py --n-students 50 --seed 20261112
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_bank import BANK, FIRST_NAMES, INTROS, LAST_NAMES, OFF_TOPIC  # noqa: E402

ITEM_DIFFICULTY = {"S1": 0.3, "S2": 0.1, "S3": -0.3, "S4": -0.5}
TR_ASCII = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o", "ü": "u"})


def add_typos(text: str, rate: float, rng: random.Random) -> str:
    """Kelime düzeyinde yazım hatası ekler: Türkçe karakter kaybı, harf düşmesi, harf yer değiştirme."""
    words = text.split(" ")
    out = []
    for w in words:
        if len(w) > 3 and rng.random() < rate:
            kind = rng.choice(["ascii", "drop", "swap"])
            if kind == "ascii" and w.translate(TR_ASCII) != w:
                w = w.translate(TR_ASCII)
            elif kind == "drop":
                i = rng.randrange(1, len(w) - 1)
                w = w[:i] + w[i + 1:]
            else:
                i = rng.randrange(0, len(w) - 2)
                w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
        out.append(w)
    return " ".join(out)


def compose(item_id: str, levels: dict[str, int], rng: random.Random, pii: str | None) -> str:
    parts: list[str] = []
    intro = rng.choice(INTROS)
    if intro:
        parts.append(intro)
    mean_level = sum(levels.values()) / len(levels)
    for cid in sorted(BANK[item_id]):
        options = BANK[item_id][cid][levels[cid]]
        if options:
            parts.append(rng.choice(options))
        # Yüksek düzeyde bazen aynı ölçüt için ikinci bir (alt düzey) cümle eklenir -> uzunluk çeşitliliği
        if levels[cid] >= 3 and rng.random() < 0.35:
            extra = BANK[item_id][cid][levels[cid] - 1]
            if extra:
                parts.append(rng.choice(extra))
    if rng.random() < max(0.05, 0.45 - 0.1 * mean_level):
        parts.insert(rng.randrange(0, len(parts) + 1), rng.choice(OFF_TOPIC))
    if pii:
        parts.insert(rng.randrange(0, len(parts) + 1), pii)
    if not parts:
        parts = [rng.choice(OFF_TOPIC)]
    text = " ".join(parts)
    typo_rate = max(0.0, 0.10 - 0.02 * mean_level) + rng.uniform(0, 0.03)
    return add_typos(text, typo_rate, rng)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-students", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", default="data/raw/moodle_export.csv")
    ap.add_argument("--truth", default="data/synthetic/latent_truth.csv")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    nrng = np.random.default_rng(args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.truth).parent.mkdir(parents=True, exist_ok=True)

    items = sorted(BANK)
    header = ["Soyadı", "Adı", "Kullanıcı adı", "ID numarası", "E-posta adresi", "Durum", "Başlangıç",
              "Tamamlandı", "Geçen süre", "Not/100,00"]
    for k in range(1, len(items) + 1):
        header += [f"Soru {k}", f"Yanıt {k}"]

    used_emails: set[str] = set()
    rows, truth_rows = [], []
    base_time = datetime(2027, 1, 15, 10, 0)
    n_pii = 0
    for s in range(args.n_students):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        uname = (first + "." + last).lower().translate(TR_ASCII).replace("İ".lower(), "i")
        email = f"{uname}{s}@ogrenci.ornek.edu.tr"
        while email in used_emails:
            email = email.replace("@", "x@")
        used_emails.add(email)
        number = str(2023000000 + rng.randrange(0, 999999))
        theta = nrng.normal()
        start = base_time + timedelta(minutes=rng.randrange(0, 15))
        row = {"Soyadı": last, "Adı": first, "Kullanıcı adı": uname, "ID numarası": number,
               "E-posta adresi": email, "Durum": "Bitti",
               "Başlangıç": start.strftime("%d %B %Y %H:%M"),
               "Tamamlandı": (start + timedelta(minutes=rng.randrange(40, 90))).strftime("%d %B %Y %H:%M"),
               "Geçen süre": f"{rng.randrange(40, 90)} dakika", "Not/100,00": "Henüz notlandırılmadı"}
        for k, item_id in enumerate(items, start=1):
            levels = {}
            for cid in sorted(BANK[item_id]):
                raw = 2 + 1.1 * theta + ITEM_DIFFICULTY[item_id] + nrng.normal(0, 0.7)
                levels[cid] = int(np.clip(np.round(raw), 0, 4))
                truth_rows.append({"email": email, "item_id": item_id, "criterion_id": cid,
                                   "true_score": levels[cid]})
            pii = None
            if rng.random() < 0.08:
                n_pii += 1
                pii = rng.choice([
                    f"Ben {first} {last}, numaram {number}.",
                    f"Adım {first}, sorularım için {email} adresine yazabilirsiniz.",
                    f"Öğrenci no: {number}",
                    f"Hocam notumu 0532 {rng.randrange(100, 999)} {rng.randrange(10, 99)} {rng.randrange(10, 99)} numarasından bildirir misiniz?",
                    f"Arkadaşım {rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)} ile birlikte çalıştık.",
                ])
            row[f"Soru {k}"] = f"[{item_id}] metni"
            # Az sayıda boş yanıt (Moodle'da "-")
            row[f"Yanıt {k}"] = "-" if rng.random() < 0.01 else compose(item_id, levels, rng, pii)
        rows.append(row)
    rows.append({h: "" for h in header} | {"Soyadı": "Genel ortalama"})

    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    with open(args.truth, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email", "item_id", "criterion_id", "true_score"])
        w.writeheader()
        w.writerows(truth_rows)
    print(f"{args.n_students} öğrenci × {len(items)} soru yazıldı -> {args.out}  (PII eklenen yanıt: {n_pii})")
    print(f"Gizli gerçek puanlar -> {args.truth}")


if __name__ == "__main__":
    main()
