"""Altın set örneklemesi, çapraz doğrulama katları ve puanlayıcı dosyaları."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from .config import ItemBank
from .utils import ensure_parent


def _allocate(sizes: pd.Series, n: int) -> pd.Series:
    """Büyük kalan yöntemiyle orantılı dağıtım (katman büyüklüğünü aşmadan)."""
    total = sizes.sum()
    raw = sizes / total * n
    alloc = np.floor(raw).astype(int).clip(upper=sizes)
    rem = (raw - np.floor(raw)).sort_values(ascending=False)
    i = 0
    while alloc.sum() < n and i < 10 * len(rem):
        k = rem.index[i % len(rem)]
        if alloc[k] < sizes[k]:
            alloc[k] += 1
        i += 1
    return alloc


def sample_gold(responses: pd.DataFrame, official: pd.DataFrame | None, bank: ItemBank, per_item: int,
                strata_bins: int, seed: int, exclude_ids: set[str] | None = None) -> pd.DataFrame:
    """Her sorudan `per_item` yanıtı katmanlara orantılı olarak seçkisiz seçer.

    Katman değişkeni: resmî toplam puan (varsa); resmî not yoksa yanıt uzunluğu (kelime sayısı) — böylece altın
    set kısa/uzun ve zayıf/güçlü yanıtları orantılı içerir. Boş yanıtlar ve çapa kaynağı yanıtlar havuz dışıdır.
    """
    rng = np.random.default_rng(seed)
    exclude_ids = exclude_ids or set()
    pool = responses[(~responses.is_empty) & (~responses.response_id.isin(exclude_ids))].copy()
    if official is not None and len(official):
        off_tot = official.groupby("response_id")["score"].sum().rename("strata_value")
        pool = pool.merge(off_tot, left_on="response_id", right_index=True, how="inner")
        basis = "resmî toplam puan"
    else:
        pool["strata_value"] = pool.text.str.split().str.len().fillna(0)
        basis = "yanıt uzunluğu (kelime)"
    out = []
    for item_id in bank.ids:
        p = pool[pool.item_id == item_id].sort_values("response_id").copy()
        n = min(per_item, len(p))
        if n < per_item:
            print(f"UYARI: {item_id} için havuzda {len(p)} yanıt var; {per_item} yerine {n} seçilecek.")
        if n == 0:
            continue
        try:
            p["stratum"] = pd.qcut(p.strata_value.rank(method="first"), q=min(strata_bins, len(p)),
                                   labels=False, duplicates="drop")
        except ValueError:
            p["stratum"] = 0
        sizes = p.groupby("stratum").size()
        alloc = _allocate(sizes, n)
        for st, k in alloc.items():
            cand = p[p.stratum == st]
            idx = rng.choice(len(cand), size=int(k), replace=False)
            out.append(cand.iloc[sorted(idx)])
    gold = pd.concat(out)[["response_id", "student_code", "item_id", "stratum", "strata_value"]]
    gold["strata_basis"] = basis
    return gold.sort_values("response_id").reset_index(drop=True)


def assign_folds(gold: pd.DataFrame, n_folds: int, seed: int) -> pd.DataFrame:
    """Öğrenci düzeyinde katlar: bir öğrencinin tüm altın set yanıtları aynı kattadır."""
    rng = np.random.default_rng(seed)
    students = np.array(sorted(gold.student_code.unique()))
    rng.shuffle(students)
    fold_of = {s: i % n_folds for i, s in enumerate(students)}
    f = gold[["response_id", "student_code", "item_id"]].copy()
    f["fold"] = f.student_code.map(fold_of).astype(int)
    return f


def write_rating_sheet(gold: pd.DataFrame, responses: pd.DataFrame, bank: ItemBank, path: str | Path,
                       seed: int) -> None:
    """Puanlayıcılar için anonim, karıştırılmış Excel dosyası. Resmî not bu dosyada YOKTUR."""
    rng = np.random.default_rng(seed)
    g = gold[["response_id", "item_id"]].merge(responses[["response_id", "text"]], on="response_id")
    wb = Workbook()
    wb.remove(wb.active)
    info = wb.create_sheet("Yönerge")
    info["A1"] = "Her yanıtı rubrikteki her ölçüt için ayrı ayrı, birbirinizden bağımsız (kör) puanlayınız."
    info["A2"] = "Yanıtların sırası rastgeledir. Öğrenci kimliği ve resmî not bu dosyada yer almaz."
    info["A3"] = "Puanları açılır listeden seçiniz; emin olmadığınız yanıtları 'Not' sütununda belirtiniz."
    for it in bank.items:
        ws = wb.create_sheet(it.item_id)
        ws["A1"] = f"{it.item_id}: {it.question}"
        ws["A1"].font = Font(bold=True)
        header = ["Sıra", "Yanıt kodu", "Yanıt metni"] + [f"{c.criterion_id} – {c.name}" for c in it.criteria] + ["Not"]
        ws.append([])
        ws.append(header)
        for cell in ws[3]:
            cell.font = Font(bold=True)
        sub = g[g.item_id == it.item_id].sample(frac=1, random_state=int(rng.integers(1 << 31)))
        for k, row in enumerate(sub.itertuples(index=False), start=1):
            ws.append([k, row.response_id, row.text] + [None] * len(it.criteria) + [None])
        n = len(sub)
        for j, c in enumerate(it.criteria):
            col = chr(ord("D") + j)
            dv = DataValidation(type="list", formula1='"' + ",".join(str(v) for v in range(c.score_min, c.score_max + 1)) + '"',
                                allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col}4:{col}{3 + n}")
        ws.column_dimensions["C"].width = 100
        for row in ws.iter_rows(min_row=4, min_col=3, max_col=3):
            row[0].alignment = Alignment(wrap_text=True, vertical="top")
        rub = wb.create_sheet(f"{it.item_id}-rubrik")
        rub.append(["Ölçüt", "Puan", "Tanımlayıcı"])
        for c in it.criteria:
            for lvl, desc in c.levels.items():
                rub.append([f"{c.criterion_id} – {c.name}", lvl, desc])
        rub.column_dimensions["C"].width = 100
    wb.save(ensure_parent(path))


def write_labelstudio(gold: pd.DataFrame, responses: pd.DataFrame, bank: ItemBank, path: str | Path,
                      seed: int) -> Path:
    """Label Studio içe aktarma JSON'u + etiketleme arayüzü yapılandırması (XML)."""
    rng = np.random.default_rng(seed)
    g = gold[["response_id", "item_id"]].merge(responses[["response_id", "text"]], on="response_id")
    g = g.sample(frac=1, random_state=int(rng.integers(1 << 31)))
    tasks = [{"data": {"response_id": r.response_id, "item_id": r.item_id, "question": bank[r.item_id].question,
                       "text": r.text}} for r in g.itertuples(index=False)]
    ensure_parent(path).write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    crits = sorted({(c.criterion_id, c.score_min, c.score_max) for it in bank.items for c in it.criteria})
    xml = ['<View>', '  <Header value="$item_id: $question"/>', '  <Text name="text" value="$text"/>']
    for cid, lo, hi in crits:
        xml.append(f'  <Header value="{cid}"/>')
        xml.append(f'  <Choices name="{cid}" toName="text" choice="single" showInline="true">')
        xml += [f'    <Choice value="{v}"/>' for v in range(lo, hi + 1)]
        xml.append('  </Choices>')
    xml.append('</View>')
    cfg = Path(path).with_suffix(".labeling_config.xml")
    cfg.write_text("\n".join(xml), encoding="utf-8")
    return cfg
