"""İnsan puanlayıcı iş akışı: kalibrasyon örneklemi, doldurulmuş Excel'lerin içe aktarılması, puanlayıcılar arası
uyum ve hakem (adjudication) dosyası.

Excel biçimi `sampling.write_rating_sheet` ile üretilen dosyadır: her soru ayrı sayfada, başlık satırında
"Yanıt kodu" ve "C1 – …", "C2 – …" sütunları; puanlar açılır listeden girilir. Hakem dosyasında puanlanması
gerekmeyen hücrelerde "—" bulunur.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from .config import ItemBank
from .metrics import qwk
from .utils import ensure_parent

HUMAN_COLUMNS = ["response_id", "rater_id", "role", "set", "criterion_id", "score"]


# ----------------------------------------------------------------------------- kalibrasyon örneklemi
def sample_calibration(responses: pd.DataFrame, gold_ids: set[str], per_item: int, seed: int,
                       exclude: set[str] | None = None) -> pd.DataFrame:
    """Altın sete GİRMEYEN yanıtlardan soru başına `per_item` yanıt (önceki kalibrasyon turları da dışlanır)."""
    rng = np.random.default_rng(seed)
    exclude = (exclude or set()) | gold_ids
    pool = responses[(~responses.is_empty) & (~responses.response_id.isin(exclude))]
    parts = []
    for item_id, g in pool.groupby("item_id"):
        g = g.sort_values("response_id")
        k = min(per_item, len(g))
        parts.append(g.iloc[sorted(rng.choice(len(g), size=k, replace=False))])
    if not parts:
        return pd.DataFrame(columns=["response_id", "student_code", "item_id"])
    return pd.concat(parts)[["response_id", "student_code", "item_id"]].reset_index(drop=True)


# ----------------------------------------------------------------------------- içe aktarma
def _criterion_from_header(h: str) -> str | None:
    m = re.match(r"^\s*(C\d+)\b", str(h or ""))
    return m.group(1) if m else None


def read_rating_workbook(path: str | Path, bank: ItemBank) -> tuple[pd.DataFrame, list[str]]:
    """Doldurulmuş puanlayıcı/hakem Excel'ini okur. (uzun biçim puanlar, uyarılar) döndürür."""
    wb = load_workbook(path, data_only=True)
    rows, warnings = [], []
    for it in bank.items:
        if it.item_id not in wb.sheetnames:
            continue
        ws = wb[it.item_id]
        header_row, header = None, None
        for r in ws.iter_rows(min_row=1, max_row=10):
            vals = [c.value for c in r]
            if any(str(v).strip().lower() == "yanıt kodu" for v in vals if v):
                header_row, header = r[0].row, vals
                break
        if header is None:
            warnings.append(f"{it.item_id}: başlık satırı ('Yanıt kodu') bulunamadı")
            continue
        id_col = next(i for i, v in enumerate(header) if v and str(v).strip().lower() == "yanıt kodu")
        crit_cols = {i: _criterion_from_header(v) for i, v in enumerate(header) if _criterion_from_header(v)}
        ranges = {c.criterion_id: (c.score_min, c.score_max) for c in it.criteria}
        for r in ws.iter_rows(min_row=header_row + 1, values_only=True):
            rid = r[id_col] if id_col < len(r) else None
            if not rid:
                continue
            for i, cid in crit_cols.items():
                v = r[i] if i < len(r) else None
                if v is None or str(v).strip() in ("", "—", "-"):
                    continue
                try:
                    score = int(float(str(v).replace(",", ".")))
                except ValueError:
                    warnings.append(f"{it.item_id}/{rid}/{cid}: sayı değil ({v!r})")
                    continue
                lo, hi = ranges.get(cid, (0, 4))
                if not lo <= score <= hi or float(str(v).replace(",", ".")) != score:
                    warnings.append(f"{it.item_id}/{rid}/{cid}: geçersiz puan {v!r} ({lo}–{hi} arası tamsayı olmalı)")
                    continue
                rows.append({"response_id": str(rid).strip(), "item_id": it.item_id, "criterion_id": cid,
                             "score": score})
    return pd.DataFrame(rows, columns=["response_id", "item_id", "criterion_id", "score"]), warnings


def merge_into_human_scores(path: str | Path, scores: pd.DataFrame, rater_id: str, role: str,
                            set_name: str) -> pd.DataFrame:
    """Aynı (puanlayıcı, rol, küme) için önceki satırları değiştirerek human_scores.csv dosyasına yazar."""
    p = Path(path)
    old = pd.read_csv(p, dtype={"response_id": str}) if p.exists() else pd.DataFrame(columns=HUMAN_COLUMNS)
    old = old[~((old.rater_id == rater_id) & (old.role == role) & (old.set == set_name))]
    new = scores.assign(rater_id=rater_id, role=role, set=set_name)[HUMAN_COLUMNS]
    out = pd.concat([old, new], ignore_index=True).sort_values(["set", "role", "response_id", "criterion_id"])
    out.to_csv(ensure_parent(p), index=False)
    return out


def completeness(scores: pd.DataFrame, expected_ids: set[str], bank: ItemBank, item_of: dict[str, str]) -> list[str]:
    """Beklenen her yanıt × ölçüt puanlanmış mı?"""
    have = set(zip(scores.response_id, scores.criterion_id))
    missing = []
    for rid in sorted(expected_ids):
        it = bank[item_of[rid]]
        miss = [c.criterion_id for c in it.criteria if (rid, c.criterion_id) not in have]
        if miss:
            missing.append(f"{rid}: {', '.join(miss)}")
    return missing


# ----------------------------------------------------------------------------- uyum
def rater_agreement(human: pd.DataFrame, set_name: str, bank: ItemBank, item_of: dict[str, str],
                    exact_target: float = 0.70, qwk_target: float = 0.80) -> pd.DataFrame:
    h = human[(human.set == set_name) & human.role.isin(["rater1", "rater2"])]
    w = h.pivot_table(index=["response_id", "criterion_id"], columns="role", values="score", aggfunc="first").dropna()
    if w.empty or not {"rater1", "rater2"} <= set(w.columns):
        return pd.DataFrame()
    w = w.reset_index()
    w["item_id"] = w.response_id.map(item_of)
    rows = []
    for (item_id, cid), g in w.groupby(["item_id", "criterion_id"]):
        c = bank[item_id].criterion(cid)
        q = qwk(g.rater1.astype(int), g.rater2.astype(int), c.score_min, c.score_max)
        ex = float((g.rater1 == g.rater2).mean())
        rows.append({"soru": item_id, "ölçüt": cid, "n": len(g), "tam_uyum": round(ex, 3),
                     "bitişik_uyum": round(float(((g.rater1 - g.rater2).abs() <= 1).mean()), 3),
                     "qwk": round(q, 3) if q == q else None,
                     "hedef": "TAMAM" if ex >= exact_target and (q == q and q >= qwk_target) else "DEĞİL"})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- hakem dosyası
def disagreements(human: pd.DataFrame, set_name: str = "gold") -> pd.DataFrame:
    h = human[(human.set == set_name) & human.role.isin(["rater1", "rater2"])]
    w = h.pivot_table(index=["response_id", "criterion_id"], columns="role", values="score", aggfunc="first")
    w = w.dropna().reset_index()
    return w[w.rater1 != w.rater2][["response_id", "criterion_id"]]


def write_adjudication_sheet(dis: pd.DataFrame, responses: pd.DataFrame, bank: ItemBank, path: str | Path,
                             seed: int) -> int:
    """Yalnızca iki puanlayıcının ayrıştığı yanıtlar; ayrışılan ölçütler boş, diğerleri '—'.
    Puanlayıcıların verdiği puanlar hakeme GÖSTERİLMEZ."""
    rng = np.random.default_rng(seed)
    text = responses.set_index("response_id").text
    item_of = responses.set_index("response_id").item_id
    wb = Workbook()
    wb.remove(wb.active)
    info = wb.create_sheet("Yönerge")
    info["A1"] = "Hakem puanlaması: yalnızca boş bırakılmış hücreleri puanlayınız ('—' olan ölçütler puanlanmaz)."
    info["A2"] = "İki puanlayıcının puanları bu dosyada gösterilmez. Rubriğe göre bağımsız puan veriniz."
    total = 0
    for it in bank.items:
        d = dis[dis.response_id.map(item_of) == it.item_id]
        if d.empty:
            continue
        ws = wb.create_sheet(it.item_id)
        ws["A1"] = f"{it.item_id}: {it.question}"
        ws["A1"].font = Font(bold=True)
        ws.append([])
        ws.append(["Sıra", "Yanıt kodu", "Yanıt metni"] + [f"{c.criterion_id} – {c.name}" for c in it.criteria] + ["Not"])
        for cell in ws[3]:
            cell.font = Font(bold=True)
        rids = sorted(d.response_id.unique())
        rng.shuffle(rids)
        need = set(zip(d.response_id, d.criterion_id))
        for k, rid in enumerate(rids, start=1):
            ws.append([k, rid, text[rid]] + [None if (rid, c.criterion_id) in need else "—" for c in it.criteria] + [None])
        for j, c in enumerate(it.criteria):
            col = chr(ord("D") + j)
            dv = DataValidation(type="list", formula1='"' + ",".join(str(v) for v in range(c.score_min, c.score_max + 1))
                                + ',—"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col}4:{col}{3 + len(rids)}")
        ws.column_dimensions["C"].width = 100
        for row in ws.iter_rows(min_row=4, min_col=3, max_col=3):
            row[0].alignment = Alignment(wrap_text=True, vertical="top")
        total += len(rids)
    wb.save(ensure_parent(path))
    return total
