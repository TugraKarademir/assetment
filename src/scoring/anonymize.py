"""Anonimleştirme: öğrenci kodları, şifreli eşleme tablosu ve metin içi kişisel veri maskeleme.

İlkeler
-------
1. Kimlik sütunları (ad, soyad, e-posta, numara, kullanıcı adı) çıktı dosyasına hiç yazılmaz.
2. Her öğrenciye rastgele (kriptografik) bir kod, her yanıta rastgele sıralı bir yanıt kodu verilir.
3. Kod <-> kimlik eşlemesi Fernet (AES-128-CBC + HMAC-SHA256) ile şifrelenmiş ayrı bir dosyada tutulur;
   anahtar `.env` içindeki MAPPING_KEY'dir. Dosya ve anahtar .gitignore kapsamındadır.
4. Yanıt metinlerinde geçen ad/numara/e-posta/telefon maskelenir; maskelenen her değer gizli bir rapora,
   yalnızca sayımlar paylaşılabilir bir özete yazılır.
5. Son denetim: bilinen e-posta, numara ve tam adların hiçbiri çıktı metninde kalmamalıdır; kalırsa hata.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken

from .moodle_io import MoodleRecord
from .utils import ensure_parent, tr_lower

WORD = r"[0-9A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû]"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?90[\s-]?)?0?\s?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
TCKN_RE = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
LONGNUM_RE = re.compile(r"(?<!\d)\d{6,12}(?!\d)")
INTRO_RE = re.compile(r"(?:\b(?:[Aa]dım|[İi]smim|[Bb]enim adım|[Bb]en)\s+)((?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?)")
INTRO_STOP = {"de", "da", "bu", "bir", "şu", "o", "ise", "Yapay", "Bence", "Sistem", "Model", "Bu", "Bir"}


# ----------------------------------------------------------------------------- şifreli eşleme
def generate_key() -> str:
    return Fernet.generate_key().decode()


def _fernet(key: str | None = None) -> Fernet:
    key = key or os.environ.get("MAPPING_KEY")
    if not key:
        raise RuntimeError("MAPPING_KEY tanımlı değil. `uv run scoring gen-key` ile anahtar üretip .env dosyasına ekleyin.")
    return Fernet(key.encode())


def save_mapping(mapping: dict, path: str | Path, key: str | None = None) -> None:
    token = _fernet(key).encrypt(json.dumps(mapping, ensure_ascii=False).encode("utf-8"))
    ensure_parent(path).write_bytes(token)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_mapping(path: str | Path, key: str | None = None) -> dict:
    try:
        return json.loads(_fernet(key).decrypt(Path(path).read_bytes()).decode("utf-8"))
    except InvalidToken as e:
        raise RuntimeError("Eşleme dosyası çözülemedi: MAPPING_KEY yanlış ya da dosya bozuk.") from e


# ----------------------------------------------------------------------------- maskeleme
@dataclass
class Finding:
    response_id: str
    pii_type: str
    value: str
    start: int
    end: int
    rule: str
    masked: bool = True


def _read_list(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


class PIIMasker:
    """Regex + kontrol listesi tabanlı maskeleme. Eşleşmeler Türkçe küçük harfli metin üzerinde aranır,
    konumlar özgün metne uygulanır (tr_lower uzunluğu korur)."""

    def __init__(self, known_names: list[str], known_numbers: list[str], known_emails: list[str],
                 denylist: list[str] | None = None, common_first_names: list[str] | None = None,
                 ambiguous_words: list[str] | None = None):
        self.ambiguous = {tr_lower(w) for w in (ambiguous_words or [])}
        names = sorted({n.strip() for n in known_names if n and len(n.strip()) >= 2}, key=len, reverse=True)
        self.known_strict = [n for n in names if tr_lower(n) not in self.ambiguous]
        self.known_capital_only = [n for n in names if tr_lower(n) in self.ambiguous]
        self.common_first = sorted({n for n in (common_first_names or [])}, key=len, reverse=True)
        self.numbers = sorted({n for n in known_numbers if n}, key=len, reverse=True)
        self.emails = sorted({e for e in known_emails if e}, key=len, reverse=True)
        self.denylist = sorted({d for d in (denylist or [])}, key=len, reverse=True)

    @staticmethod
    def _word_pattern(words: list[str]) -> re.Pattern | None:
        if not words:
            return None
        alt = "|".join(re.escape(tr_lower(w)) for w in words)
        return re.compile(rf"(?<!{WORD})(?:{alt})(?!{WORD})")

    def find(self, text: str) -> list[tuple[int, int, str, str, bool]]:
        """(başlangıç, bitiş, tür, kural, maskelenecek_mi) listesi döndürür."""
        low = tr_lower(text)
        assert len(low) == len(text)
        spans: list[tuple[int, int, str, str, bool]] = []

        for m in EMAIL_RE.finditer(text):
            spans.append((m.start(), m.end(), "EPOSTA", "regex:email", True))
        for e in self.emails:
            for m in re.finditer(re.escape(tr_lower(e)), low):
                spans.append((m.start(), m.end(), "EPOSTA", "liste:email", True))
        for m in PHONE_RE.finditer(text):
            spans.append((m.start(), m.end(), "TELEFON", "regex:telefon", True))
        for n in self.numbers:
            for m in re.finditer(rf"(?<!\d){re.escape(n)}(?!\d)", text):
                spans.append((m.start(), m.end(), "NUMARA", "liste:numara", True))
        for m in TCKN_RE.finditer(text):
            spans.append((m.start(), m.end(), "TCKN", "regex:11hane", True))
        for m in LONGNUM_RE.finditer(text):
            spans.append((m.start(), m.end(), "NUMARA", "regex:6-12hane", True))

        if (p := self._word_pattern(self.known_strict)):
            for m in p.finditer(low):
                spans.append((m.start(), m.end(), "AD", "liste:öğrenci-adları", True))
        if (p := self._word_pattern(self.known_capital_only)):
            for m in p.finditer(low):
                cap = text[m.start()].isupper()
                spans.append((m.start(), m.end(), "AD", "liste:öğrenci-adları(belirsiz)", cap))
        if (p := self._word_pattern(self.common_first)):
            for m in p.finditer(low):
                if text[m.start()].isupper():
                    spans.append((m.start(), m.end(), "AD", "liste:yaygın-adlar", True))
                    # Hemen ardından büyük harfli bir sözcük gelirse soyadı say
                    nxt = re.match(rf"\s+([A-ZÇĞİÖŞÜ]{WORD}+)", text[m.end():])
                    if nxt:
                        s = m.end() + nxt.start(1)
                        spans.append((s, s + len(nxt.group(1)), "AD", "sezgisel:ad-sonrası-soyad", True))
        for m in INTRO_RE.finditer(text):
            g = m.group(1)
            if g.split()[0] not in INTRO_STOP:
                spans.append((m.start(1), m.end(1), "AD", "sezgisel:tanıtım-kalıbı", True))
        if (p := self._word_pattern(self.denylist)):
            for m in p.finditer(low):
                spans.append((m.start(), m.end(), "MASKE", "liste:yasak-terimler", True))
        return self._merge(spans)

    @staticmethod
    def _merge(spans):
        """Çakışan aralıkları birleştirir; maskelenecek olan öncelikli."""
        spans = sorted(spans, key=lambda x: (x[0], -(x[1] - x[0])))
        out: list[list] = []
        for s in spans:
            if out and s[0] < out[-1][1]:
                last = out[-1]
                last[1] = max(last[1], s[1])
                if s[4] and not last[4]:
                    last[2], last[3], last[4] = s[2], s[3], True
                continue
            out.append(list(s))
        return [tuple(x) for x in out]

    def mask(self, text: str, response_id: str = "") -> tuple[str, list[Finding]]:
        spans = self.find(text)
        findings = [Finding(response_id, t, text[s:e], s, e, rule, masked) for s, e, t, rule, masked in spans]
        out = text
        for s, e, t, _rule, masked in sorted(spans, key=lambda x: x[0], reverse=True):
            if masked:
                out = out[:s] + f"[{t}]" + out[e:]
        return out, findings


# ----------------------------------------------------------------------------- ana işlem
def _student_key(identity: dict[str, str]) -> str:
    for k in ("email", "id_number", "username"):
        if identity.get(k):
            return f"{k}:{tr_lower(identity[k].strip())}"
    raise ValueError("Öğrenci anahtarı yok")


def anonymize_records(records: list[MoodleRecord], mapping_path: str | Path, responses_out: str | Path,
                      pii_private_out: str | Path, pii_summary_out: str | Path,
                      denylist_path: str | Path = "config/pii_denylist.txt",
                      first_names_path: str | Path = "config/tr_first_names.txt",
                      ambiguous_path: str | Path = "config/pii_ambiguous_words.txt",
                      key: str | None = None) -> pd.DataFrame:
    sysrand = secrets.SystemRandom()
    mapping = load_mapping(mapping_path, key) if Path(mapping_path).exists() else {"students": {}, "responses": {}}
    students: dict[str, dict] = mapping["students"]          # student_key -> {code, identity}
    responses_map: dict[str, dict] = mapping["responses"]    # "student_code|item_id" -> response_id

    used_codes = {v["code"] for v in students.values()}
    new_keys = sorted({_student_key(r.identity) for r in records} - set(students))
    sysrand.shuffle(new_keys)
    for k in new_keys:
        while True:
            code = "P" + secrets.token_hex(3).upper()
            if code not in used_codes:
                break
        used_codes.add(code)
        ident = next(r.identity for r in records if _student_key(r.identity) == k)
        students[k] = {"code": code, "identity": ident}

    pending = [(students[_student_key(r.identity)]["code"], r.item_id) for r in records]
    new_pairs = [p for p in dict.fromkeys(pending) if f"{p[0]}|{p[1]}" not in responses_map]
    sysrand.shuffle(new_pairs)
    used_ids = {int(v[1:]) for v in responses_map.values()}
    nxt = max(used_ids, default=0) + 1
    for p in new_pairs:
        responses_map[f"{p[0]}|{p[1]}"] = f"R{nxt:05d}"
        nxt += 1

    # Maskeleme listeleri
    idents = [s["identity"] for s in students.values()]
    known_names = []
    for i in idents:
        fn, ln = i.get("first_name", ""), i.get("last_name", "")
        known_names += [fn, ln, f"{fn} {ln}".strip()] + fn.split() + ln.split()
    masker = PIIMasker(
        known_names=known_names,
        known_numbers=[i.get("id_number", "") for i in idents],
        known_emails=[i.get("email", "") for i in idents] + [i.get("username", "") for i in idents if len(i.get("username", "")) >= 5],
        denylist=_read_list(denylist_path),
        common_first_names=_read_list(first_names_path),
        ambiguous_words=_read_list(ambiguous_path),
    )

    rows, findings = [], []
    for r in records:
        code = students[_student_key(r.identity)]["code"]
        rid = responses_map[f"{code}|{r.item_id}"]
        masked, f = masker.mask(r.text, rid)
        findings += f
        rows.append({"response_id": rid, "student_code": code, "item_id": r.item_id, "text": masked,
                     "is_empty": r.is_empty, "n_masked": sum(x.masked for x in f),
                     "n_flagged_unmasked": sum(not x.masked for x in f)})
    df = pd.DataFrame(rows).sort_values("response_id").reset_index(drop=True)

    _final_leak_check(df, idents)

    save_mapping({"students": students, "responses": responses_map}, mapping_path, key)
    df.to_csv(ensure_parent(responses_out), index=False)
    fdf = pd.DataFrame([asdict(x) for x in findings],
                       columns=["response_id", "pii_type", "value", "start", "end", "rule", "masked"])
    fdf.to_csv(ensure_parent(pii_private_out), index=False)
    summary = (fdf.groupby(["pii_type", "rule", "masked"]).size().reset_index(name="n")
               if len(fdf) else pd.DataFrame(columns=["pii_type", "rule", "masked", "n"]))
    summary.to_csv(ensure_parent(pii_summary_out), index=False)
    return df


def _final_leak_check(df: pd.DataFrame, idents: list[dict]) -> None:
    blob = tr_lower("\n".join(df["text"].astype(str)))
    leaks = []
    for i in idents:
        for k in ("email", "id_number"):
            v = i.get(k, "")
            if v and tr_lower(v) in blob:
                leaks.append(k)
        full = f"{i.get('first_name', '')} {i.get('last_name', '')}".strip()
        if len(full) > 3 and re.search(rf"(?<!{WORD}){re.escape(tr_lower(full))}(?!{WORD})", blob):
            leaks.append("full_name")
    if leaks:
        raise RuntimeError(f"Maskeleme sonrası kimlik sızıntısı tespit edildi ({len(leaks)} adet: {sorted(set(leaks))}). "
                           "Çıktı yazılmadı.")
