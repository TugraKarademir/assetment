"""Onam filtresi: yalnızca araştırmaya katılmayı onaylayan öğrencilerin yanıtları işlenir.

Onam dosyası (CSV ya da XLSX), onay veren öğrencilerin tanımlayıcılarını içerir: e-posta, öğrenci numarası ya da
kullanıcı adı sütunlarından en az biri (başlıklar config/moodle_columns.yaml > identity ile eşleştirilir) ya da
başlığı ne olursa olsun TEK sütunlu bir liste. Dosya isteğe bağlı bir "onam" sütunu içerebilir; varsa yalnızca
"evet / kabul / onaylıyorum / 1 / true / x" satırları onay sayılır.

Dosya kimlik bilgisi içerdiğinden data/private/ altında tutulmalıdır (gitignore).
"""
from __future__ import annotations

from pathlib import Path

from .moodle_io import IDENTITY_FIELDS, MoodleRecord, norm_header, read_table
from .utils import tr_lower

YES = {"evet", "kabul", "kabul ediyorum", "onaylıyorum", "onayliyorum", "onay", "1", "true", "x", "yes", "✓"}
CONSENT_HEADERS = {"onam", "onay", "rıza", "riza", "consent", "kabul"}


def _norm(v) -> str:
    return tr_lower(str(v)).strip()


def load_consent(path: str | Path, colmap: dict) -> set[str]:
    df = read_table(path)
    cols = {norm_header(c): c for c in df.columns}
    consent_col = next((cols[h] for h in cols if h in {norm_header(x) for x in CONSENT_HEADERS}), None)
    if consent_col is not None:
        df = df[df[consent_col].map(lambda v: _norm(v) in YES)]
    id_cols = []
    for field in IDENTITY_FIELDS:
        if field in ("first_name", "last_name"):
            continue
        for syn in colmap["identity"].get(field, []):
            if norm_header(syn) in cols:
                id_cols.append(cols[norm_header(syn)])
    if not id_cols:
        data_cols = [c for c in df.columns if c != consent_col]
        if len(data_cols) != 1:
            raise ValueError("Onam dosyasında e-posta / öğrenci numarası / kullanıcı adı sütunu bulunamadı. "
                             "Bu sütunlardan birini ekleyin ya da tek sütunlu bir liste kullanın.")
        id_cols = data_cols
    ids = {_norm(v) for c in id_cols for v in df[c] if _norm(v) and _norm(v) != "nan"}
    if not ids:
        raise ValueError("Onam dosyasında onay veren öğrenci bulunamadı.")
    return ids


def filter_records(records: list[MoodleRecord], consent_ids: set[str]) -> tuple[list[MoodleRecord], dict]:
    def consented(r: MoodleRecord) -> bool:
        return any(_norm(r.identity.get(k, "")) in consent_ids for k in ("email", "id_number", "username")
                   if r.identity.get(k))
    kept = [r for r in records if consented(r)]
    students_all = {tuple(sorted(r.identity.items())) for r in records}
    students_kept = {tuple(sorted(r.identity.items())) for r in kept}
    matched_ids = {_norm(r.identity.get(k, "")) for r in kept for k in ("email", "id_number", "username")}
    stats = {"students_in_export": len(students_all), "students_consented": len(students_kept),
             "students_excluded_no_consent": len(students_all) - len(students_kept),
             "consent_ids_not_in_export": len(consent_ids - matched_ids)}
    return kept, stats
