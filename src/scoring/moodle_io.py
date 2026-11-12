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
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str).fillna("")
    for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return pd.read_csv(path, dtype=str, sep=None, engine="python", encoding=enc).fillna("")
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


def read_moodle_export(path: str | Path, colmap: dict) -> list[MoodleRecord]:
    df = read_table(path)
    identity_cols, meta_cols, response_cols = resolve_columns(list(df.columns), colmap)
    item_map = {int(k): v for k, v in colmap["item_map"].items()}
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
