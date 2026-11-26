"""Moodle "Yanıtlar" raporu okuyucu (CSV/XLSX, Türkçe/İngilizce başlıklar).

Okuyucu yalnızca kimlik sütunlarını (kod üretimi ve maskeleme için) ve yanıt sütunlarını okur.
Diğer tüm sütunlar (IP, kurum, bölüm, süre, not ...) belleğe alınmaz/çıktıya taşınmaz.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from .utils import tr_lower

IDENTITY_FIELDS = ("last_name", "first_name", "email", "id_number", "username")


@dataclass
class MoodleRecord:
    identity: dict[str, str]
    item_id: str
    text: str
    is_empty: bool


def norm_header(h: str) -> str:
    h = tr_lower(str(h)).strip()
    h = h.translate(str.maketrans("çğıöşü", "cgiosu"))
    return re.sub(r"\s+", " ", h)


def load_column_map(path: str | Path = "config/moodle_columns.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".numbers":
        raise ValueError("Apple Numbers dosyası (.numbers) okunamaz. Numbers'ta açıp Dosya > Şuraya Dışa Aktar > "
                         "Excel ile .xlsx olarak kaydedin.")
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str).fillna("")
    for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                header = f.readline()
            # Tek sütunlu dosyada ayırıcı tahmini yanılabilir (ör. e-postadaki "@"): başlıkta ayırıcı yoksa virgül
            sep = None if any(c in header for c in ",;\t") else ","
            return pd.read_csv(path, dtype=str, sep=sep, engine="python", encoding=enc).fillna("")
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Dosya okunamadı: {path}")


def clean_text(raw: str) -> str:
    t = html.unescape(str(raw)).replace("\xa0", " ")
    t = re.sub(r"<\s*br\s*/?>|</p>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def resolve_columns(columns: list[str], colmap: dict) -> tuple[dict[str, str], dict[str, str], dict[int, str]]:
    normed = {norm_header(c): c for c in columns}

    def find(synonyms: list[str]) -> str | None:
        for s in synonyms:
            if norm_header(s) in normed:
                return normed[norm_header(s)]
        return None

    identity = {f: find(colmap["identity"].get(f, [])) for f in IDENTITY_FIELDS}
    identity = {k: v for k, v in identity.items() if v}
    meta = {k: find(v) for k, v in colmap.get("meta", {}).items()}
    meta = {k: v for k, v in meta.items() if v}
    responses: dict[int, str] = {}
    for c in columns:
        for pat in colmap["response_patterns"]:
            m = re.match(pat, norm_header(c))
            if m:
                responses[int(m.group(1))] = c
    if not responses:
        raise ValueError("Yanıt sütunu bulunamadı; config/moodle_columns.yaml > response_patterns kontrol edin. "
                         f"Başlıklar: {columns}")
    if "email" not in identity and "id_number" not in identity and "username" not in identity:
        raise ValueError("Öğrenciyi tekil tanımlayan bir sütun (e-posta/numara/kullanıcı adı) bulunamadı.")
    return identity, meta, responses


def parse_item_map(spec: str | None, colmap: dict) -> dict[int, str]:
    """'5=S1,6=S2' biçimindeki komut satırı eşlemesi; verilmezse moodle_columns.yaml > item_map."""
    if spec:
        out = {}
        for part in spec.split(","):
            k, v = part.split("=")
            out[int(k.strip())] = v.strip()
        return out
    return {int(k): v for k, v in colmap["item_map"].items()}


def inspect_export(path: str | Path, colmap: dict) -> dict:
    """Dışa aktarımın yapısını özetler. ÖĞRENCİ YANITLARINI ya da kimlik bilgilerini YAZDIRMAZ;
    yalnızca sütun adları, sayımlar ve (varsa) Moodle'ın 'Soru N' sütunlarındaki soru metinlerinin başı."""
    df = read_table(path)
    identity_cols, meta_cols, response_cols = resolve_columns(list(df.columns), colmap)
    qcols = {}
    for c in df.columns:
        m = re.match(r"^(?:soru|question)\s*(\d+)$", norm_header(c))
        if m:
            qcols[int(m.group(1))] = c
    empty = {tr_lower(e).strip() for e in colmap.get("empty_markers", [])}
    rows = []
    for n, col in sorted(response_cols.items()):
        vals = df[col].astype(str).map(clean_text)
        filled = vals[~vals.map(lambda v: tr_lower(v).strip() in empty)]
        qtext = ""
        if n in qcols:
            qv = df[qcols[n]].astype(str).map(clean_text)
            qv = qv[qv.str.len() > 0]
            qtext = (qv.iloc[0][:90] + "…") if len(qv) else ""
        rows.append({"no": n, "sutun": col, "dolu_yanit": int(len(filled)),
                     "ort_kelime": round(float(filled.str.split().str.len().mean()), 1) if len(filled) else 0.0,
                     "soru_metni_basi": qtext})
    return {"n_rows": len(df), "identity": identity_cols, "meta": meta_cols, "responses": rows,
            "other_columns": [c for c in df.columns if c not in set(identity_cols.values()) | set(meta_cols.values())
                              | set(response_cols.values()) | set(qcols.values())]}


def read_moodle_export(path: str | Path, colmap: dict, item_map: dict[int, str] | None = None) -> list[MoodleRecord]:
    df = read_table(path)
    identity_cols, meta_cols, response_cols = resolve_columns(list(df.columns), colmap)
    item_map = item_map or {int(k): v for k, v in colmap["item_map"].items()}
    finished = {tr_lower(s) for s in colmap.get("finished_states", [])}
    markers = [tr_lower(m) for m in colmap.get("drop_row_markers", [])]
    empty = {tr_lower(e).strip() for e in colmap.get("empty_markers", [])}

    records: list[MoodleRecord] = []
    for _, row in df.iterrows():
        rowtext = tr_lower(" ".join(str(row[c]) for c in identity_cols.values()))
        if any(m in rowtext for m in markers):
            continue
        if finished and "state" in meta_cols and tr_lower(row[meta_cols["state"]]) not in finished:
            continue
        identity = {k: str(row[c]).strip() for k, c in identity_cols.items()}
        if not any(identity.get(k) for k in ("email", "id_number", "username")):
            continue
        for qnum, col in sorted(response_cols.items()):
            if qnum not in item_map:
                continue
            text = clean_text(row[col])
            is_empty = tr_lower(text).strip() in empty
            records.append(MoodleRecord(identity, item_map[qnum], "" if is_empty else text, is_empty))
    return records
