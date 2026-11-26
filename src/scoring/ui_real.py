"""Arayüz: "Gerçek veri" sekmesi — onamlı veriyle uçtan uca akış (komut satırı gerektirmez).

Her adım, komut satırındaki `scoring ...` komutlarının aynısını çalıştırır; böylece arayüz ve komut satırı aynı
sonucu verir ve her şey kayda geçer. Yüklenen dosyalar yalnızca bu bilgisayardaki proje klasörüne yazılır.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from scoring.config import load_experiment, load_items

RAW_DIR, PRIV_DIR, DERIVED = Path("data/raw"), Path("data/private"), Path("data/derived")
JOB_FILE = DERIVED / "ui_job.json"
CANARY = Path("config/canary.local.yaml")


# ----------------------------------------------------------------------------- yardımcılar
def run_cli(args: list[str], timeout: int = 3600) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-m", "scoring.cli", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=dict(os.environ, PYTHONUTF8="1"))
    out = (p.stdout + ("\n" + p.stderr if p.stderr.strip() else "")).strip()
    # Streamlit/typer hata çerçevelerini kısalt
    if p.returncode != 0 and "Traceback" in out:
        out = "\n".join(ln for ln in out.splitlines() if not ln.startswith(("│", "╭", "╰")))[-3000:]
    return p.returncode, out


def show_result(code: int, out: str) -> None:
    (st.success if code == 0 else st.error)("Tamamlandı" if code == 0 else f"Hata (çıkış kodu {code})")
    if out:
        st.code(out)


NUMBERS_HELP = ("Bu bir Apple **Numbers** dosyası (.numbers); program Excel ya da CSV okur. Dosyayı Numbers'ta açıp "
                "**Dosya → Şuraya Dışa Aktar → Excel…** ile `.xlsx` olarak kaydedin ve onu yükleyin.")


def not_numbers(up) -> bool:
    """Dosya seçildiyse ve Numbers dosyası değilse True; Numbers dosyasıysa açıklama gösterir."""
    if up is not None and up.name.lower().endswith(".numbers"):
        st.error(NUMBERS_HELP)
        return False
    return up is not None


def act(step: str, args: list[str], spinner: str = "Çalışıyor…") -> None:
    """Komutu çalıştırır, sonucu saklar ve sayfayı yeniler (durum çubuğu güncellensin, çıktı kaybolmasın)."""
    with st.spinner(spinner):
        st.session_state[f"res_{step}"] = run_cli(args)
    st.rerun()


def last_result(step: str) -> None:
    res = st.session_state.get(f"res_{step}")
    if res:
        show_result(*res)


def find_file(folder: Path, stem: str) -> Path | None:
    for ext in (".xlsx", ".xls", ".csv"):
        p = folder / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def save_upload(upl, folder: Path, stem: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for ext in (".xlsx", ".xls", ".csv"):          # aynı adlı eski dosyayı kaldır (karışmasın)
        old = folder / f"{stem}{ext}"
        if old.exists():
            old.unlink()
    ext = Path(upl.name).suffix.lower()
    dest = folder / f"{stem}{ext}"
    dest.write_bytes(upl.getbuffer())
    return dest


def is_synthetic() -> bool:
    return Path("data/synthetic/latent_truth.csv").exists()


def download(path: Path, label: str, key: str) -> None:
    if path.exists():
        st.download_button(label, path.read_bytes(), path.name, key=key)


def step_done(flag: bool) -> str:
    return "✅" if flag else "⬜"


# ----------------------------------------------------------------------------- arka plan işi
def clear_old_results() -> None:
    """Depoyla gelen ÖRNEK (sentetik) sonuçları ilk gerçek çalıştırmadan önce siler; gerçek sonuçlarla karışmasınlar.
    Anonimleştirme ve gizli işaret özetleri, günlükler, önbellek ve manifestler korunur."""
    rdir = Path("results")
    readme = rdir / "README.md"
    if not (readme.exists() and "sentetik" in readme.read_text(encoding="utf-8").lower()):
        return
    keep = {".gitkeep", "pii_summary.csv", "canary_summary.csv"}
    for f in list(rdir.glob("*.csv")) + list(rdir.glob("*.md")) + list((rdir / "figures").glob("*.png")) \
            + list((rdir / "bias").glob("*.*")):
        if f.name not in keep:
            f.unlink()


def start_job(commands: list[list[str]], label: str) -> None:
    """CLI komutlarını sırayla, arka planda (tarayıcı kapansa da sürer) çalıştırır; çıktı günlüğe yazılır."""
    log = Path("logs") / f"ui_job_{datetime.now():%Y%m%d_%H%M%S}.log"
    log.parent.mkdir(exist_ok=True)
    code = ("import subprocess,sys\n"
            f"cmds={commands!r}\n"
            "for c in cmds:\n"
            "    print('\\n$ scoring '+' '.join(c), flush=True)\n"
            "    r=subprocess.call([sys.executable,'-m','scoring.cli',*c])\n"
            "    if r!=0:\n"
            "        print(f'ADIM BAŞARISIZ (çıkış {r})', flush=True); sys.exit(r)\n"
            "print('\\nTÜM ADIMLAR TAMAMLANDI', flush=True)\n")
    kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000200}  # yeni süreç grubu
    with open(log, "w", encoding="utf-8") as f:
        proc = subprocess.Popen([sys.executable, "-u", "-c", code], stdout=f, stderr=subprocess.STDOUT,
                                env=dict(os.environ, PYTHONUTF8="1"), **kw)
    JOB_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOB_FILE.write_text(json.dumps({"pid": proc.pid, "log": str(log), "label": label,
                                    "started": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")


def job_status() -> dict | None:
    if not JOB_FILE.exists():
        return None
    job = json.loads(JOB_FILE.read_text(encoding="utf-8"))
    alive = True
    try:
        os.kill(job["pid"], 0)
    except OSError:
        alive = False
    if alive and os.name != "nt":
        try:  # zombi (bitmiş) süreç denetimi
            with open(f"/proc/{job['pid']}/status") as f:
                alive = "State:\tZ" not in f.read()
        except OSError:
            pass
    text = Path(job["log"]).read_text(encoding="utf-8", errors="replace") if Path(job["log"]).exists() else ""
    job["running"] = alive and "TÜM ADIMLAR TAMAMLANDI" not in text and "ADIM BAŞARISIZ" not in text
    job["tail"] = "\n".join(ln for ln in text.splitlines() if ln.strip() and "it/s]" not in ln)[-4000:]
    job["ok"] = "TÜM ADIMLAR TAMAMLANDI" in text
    return job


# ----------------------------------------------------------------------------- sekme
def render(models_path: str) -> None:
    exp, bank = load_experiment(), load_items()
    export = find_file(RAW_DIR, "moodle_export")
    consent = find_file(PRIV_DIR, "onam")
    responses_ok = exp.path("responses").exists() and not is_synthetic()
    gold_ok = exp.path("gold_sample").exists() and responses_ok
    hs = exp.path("human_scores")
    human = pd.read_csv(hs, dtype=str) if hs.exists() else pd.DataFrame(columns=["role", "set"])
    rated = responses_ok and {"rater1", "rater2"} <= set(human[human.set == "gold"].role) if len(human) else False
    models_ok = exp.path("condition_scores").exists() and responses_ok

    st.info("🔒 Bu arayüz yalnızca bu bilgisayarda çalışır. Yüklediğiniz dosyalar proje klasörüne (`data/`) "
            "kaydedilir; hiçbir yere gönderilmez. Öğrenci verilerini e-posta, bulut ya da yapay zekâ sohbetleriyle "
            "paylaşmayın. Yanıtlar ancak **etik kurul onayından sonra** ve yalnızca **onam veren** öğrencilerle "
            "işlenmelidir.")
    st.markdown(" · ".join([f"{step_done(bool(export))} Dosya", f"{step_done(responses_ok)} Anonimleştirme",
                            f"{step_done(gold_ok)} Altın set", f"{step_done(rated)} İnsan puanları",
                            f"{step_done(models_ok)} Model puanları"]))

    if is_synthetic():
        st.warning("Proje klasöründe **sentetik deneme verileri** var. Gerçek veriye geçmeden önce bunları "
                   "temizleyin; aksi hâlde sentetik öğrenci kodları gerçek verilerle karışır.")
        ok = st.checkbox("Sentetik deneme verilerinin (data/ altındaki işlenmiş dosyalar) silineceğini anladım")
        if st.button("Sentetik verileri temizle", disabled=not ok):
            for p in [Path("data/raw"), Path("data/processed"), Path("data/derived"), Path("data/synthetic")]:
                if p.exists():
                    shutil.rmtree(p)
            for f in [Path("data/private/mapping.enc"), Path("data/private/pii_report.csv"), Path("data/human_scores.csv")]:
                if f.exists():
                    f.unlink()
            st.success("Temizlendi.")
            st.rerun()
        return

    # 1 ------------------------------------------------------------------------------------------------ dosyalar
    with st.expander(f"{step_done(bool(export and consent))} 1. Dosyaları yükleyin", expanded=not (export and consent)):
        c1, c2 = st.columns(2)
        with c1:
            up = st.file_uploader("Moodle dışa aktarımı (Sınav > Sonuçlar > Yanıtlar; Excel ya da CSV)",
                                  type=["xlsx", "xls", "csv", "numbers"], key="up_export")
            if not_numbers(up) and st.button("Dışa aktarımı kaydet"):
                save_upload(up, RAW_DIR, "moodle_export")
                st.success("Kaydedildi: data/raw/")
                st.rerun()
            st.caption(f"Mevcut: `{export}`" if export else "Henüz yüklenmedi.")
        with c2:
            upc = st.file_uploader("Onam verenlerin listesi (e-posta / öğrenci no / kullanıcı adı; isteğe bağlı "
                                   "'Onam' sütunu)", type=["xlsx", "xls", "csv", "numbers"], key="up_consent")
            if not_numbers(upc) and st.button("Onam listesini kaydet"):
                save_upload(upc, PRIV_DIR, "onam")
                st.success("Kaydedildi: data/private/")
                st.rerun()
            st.caption(f"Mevcut: `{consent}`" if consent else "Henüz yüklenmedi.")

    # 2-3 ----------------------------------------------------------------------------- inceleme, eşleme, anonim
    with st.expander(f"{step_done(responses_ok)} 2. İnceleyin ve anonimleştirin", expanded=bool(export) and not responses_ok):
        if not export:
            st.caption("Önce dışa aktarımı yükleyin.")
        else:
            from scoring.moodle_io import inspect_export, load_column_map
            try:
                info = inspect_export(export, load_column_map())
            except Exception as e:
                st.error(f"Dosya okunamadı: {e}")
                info = None
            if info:
                st.caption(f"{info['n_rows']} satır · kimlik sütunları: "
                           + (", ".join(info["identity"].values()) or "BULUNAMADI")
                           + " · öğrenci yanıtları burada gösterilmez")
                rdf = pd.DataFrame(info["responses"])
                st.dataframe(rdf, hide_index=True, width="stretch")
                st.markdown("**Hangi Moodle sorusu hangi araştırma sorusu?**")
                options = [int(n) for n in rdf["no"]]
                labels = {int(r.no): f"Soru {r.no} — {r.soru_metni_basi or r.sutun}" for r in rdf.itertuples()}
                mapping = {}
                for i, it in enumerate(bank.items):
                    guess = next((int(r.no) for r in rdf.itertuples()
                                  if r.soru_metni_basi and it.question[:25].lower() in str(r.soru_metni_basi).lower()),
                                 options[min(len(options) - 1, len(options) - len(bank.items) + i)])
                    mapping[it.item_id] = st.selectbox(f"{it.item_id}: {it.question[:70]}…", options,
                                                       index=options.index(guess), format_func=lambda n: labels[n],
                                                       key=f"map_{it.item_id}")
                spec = ",".join(f"{n}={iid}" for iid, n in mapping.items())
                if len(set(mapping.values())) < len(mapping):
                    st.error("İki araştırma sorusu aynı Moodle sorusuna eşlenmiş.")
                elif not consent:
                    st.warning("Onam listesi yüklenmeden anonimleştirme yapılamaz.")
                elif st.button("Anonimleştir (yalnızca onam verenler)", type="primary"):
                    act("anon", ["anonymize", "--export", str(export), "--consent", str(consent), "--item-map", spec],
                        "Anonimleştiriliyor…")
                last_result("anon")
        if responses_ok:
            ps = exp.path("pii_summary")
            if ps.exists():
                st.markdown("**Maskeleme özeti**")
                st.dataframe(pd.read_csv(ps), hide_index=True)
            pr = exp.path("pii_report_private")
            if pr.exists():
                with st.expander("Maskelenen değerler (gizli rapor — elle kontrol edin)"):
                    st.caption("Gözden kaçan bir ad görürseniz config/pii_denylist.txt dosyasına ekleyip "
                               "anonimleştirmeyi yeniden çalıştırın.")
                    st.dataframe(pd.read_csv(pr), hide_index=True, width="stretch")
            st.warning("Yedek alın: `data/private/mapping.enc` ve `.env` içindeki `MAPPING_KEY` (kurum içinde, şifreli).")

    # 4 ---------------------------------------------------------------------------------------- gizli işaret
    with st.expander("3. Gizli işaret taraması (kullandıysanız)"):
        cur = yaml.safe_load(CANARY.read_text(encoding="utf-8")) if CANARY.exists() else {"items": {}}
        cur_items = cur.get("items") or {}
        new = {}
        for it in bank.items:
            terms = (cur_items.get(it.item_id) or {}).get("detect", []) if isinstance(cur_items.get(it.item_id), dict) else []
            val = st.text_input(f"{it.item_id} için aranacak uydurma ifadeler (virgülle)", ", ".join(terms),
                                key=f"can_{it.item_id}")
            new[it.item_id] = [t.strip() for t in val.split(",") if t.strip()]
        c1, c2 = st.columns(2)
        if c1.button("İfadeleri kaydet"):
            for iid, terms in new.items():
                cur_items.setdefault(iid, {})
                if not isinstance(cur_items[iid], dict):
                    cur_items[iid] = {}
                cur_items[iid]["detect"] = terms
            CANARY.write_text(yaml.safe_dump({"items": cur_items}, allow_unicode=True, sort_keys=False), encoding="utf-8")
            st.success("Kaydedildi (config/canary.local.yaml — GitHub'a gitmez).")
        if c2.button("Tara", disabled=not responses_ok):
            act("canary", ["check-canary"])
        last_result("canary")

    # 5 ------------------------------------------------------------------------------- altın set, kalibrasyon
    with st.expander(f"{step_done(gold_ok)} 4. Altın set ve puanlayıcı dosyaları", expanded=responses_ok and not gold_ok):
        if not responses_ok:
            st.caption("Önce anonimleştirin.")
        else:
            n_avail = pd.read_csv(exp.path("responses")).query("not is_empty").groupby("item_id").size()
            st.caption("Soru başına yanıt: " + ", ".join(f"{k}: {v}" for k, v in n_avail.items()))
            per = st.number_input("Soru başına altın set büyüklüğü", 10, 1000, int(min(300, n_avail.min())), step=10)
            if st.button("Altın seti seç"):
                act("gold", ["sample-gold", "--per-item", str(per)])
            last_result("gold")
            download(exp.path("gold_excel"), "⬇ Altın set puanlama dosyası (Excel)", "dl_gold")
            st.divider()
            c1, c2 = st.columns(2)
            rnd = c1.number_input("Kalibrasyon turu", 1, 5, 1)
            cper = c2.number_input("Soru başına kalibrasyon yanıtı", 5, 50, 10)
            if st.button("Kalibrasyon dosyası oluştur", disabled=not gold_ok):
                act("cal", ["calibration-sheet", "--round", str(rnd), "--per-item", str(cper)])
            last_result("cal")
            download(DERIVED / f"calibration_round{rnd}.xlsx", f"⬇ Kalibrasyon turu {rnd} (Excel)", f"dl_cal{rnd}")

    # 6 -------------------------------------------------------------------------- puanları yükle, uyum, hakem
    with st.expander(f"{step_done(rated)} 5. Doldurulmuş puanlayıcı dosyalarını yükleyin", expanded=gold_ok and not models_ok):
        if not gold_ok:
            st.caption("Önce altın seti seçin.")
        else:
            c1, c2, c3 = st.columns(3)
            rid = c1.text_input("Puanlayıcı kodu (ad yazmayın)", "H1")
            role = c2.selectbox("Rol", ["rater1", "rater2", "adjudicator", "official"],
                                format_func={"rater1": "1. puanlayıcı", "rater2": "2. puanlayıcı",
                                             "adjudicator": "hakem", "official": "resmî not"}.get)
            sets = ["gold"] + [f"calibration{p.stem[17:]}" for p in sorted(DERIVED.glob("calibration_round*.csv"))]
            set_name = c3.selectbox("Küme", sets + ["official"],
                                    format_func=lambda s: "altın set" if s == "gold" else s)
            upr = st.file_uploader("Doldurulmuş Excel", type=["xlsx", "numbers"], key="up_rating")
            if not_numbers(upr) and st.button("İçe aktar", type="primary"):
                dest = save_upload(upr, PRIV_DIR / "ratings", f"{set_name}_{role}_{rid}")
                act("imp", ["import-ratings", "--file", str(dest), "--rater-id", rid, "--role", role, "--set", set_name])
            last_result("imp")
            st.divider()
            c1, c2 = st.columns(2)
            agr_set = c1.selectbox("Uyumuna bakılacak küme", sets, key="agr_set",
                                   format_func=lambda s: "altın set" if s == "gold" else s)
            if c1.button("Puanlayıcı uyumunu göster"):
                act("agr", ["rater-agreement", "--set", agr_set])
            if c2.button("Hakem dosyası oluştur"):
                act("adj", ["adjudication-sheet"])
            last_result("agr")
            last_result("adj")
            download(DERIVED / "adjudication_sheet.xlsx", "⬇ Hakem dosyası (Excel)", "dl_adj")

    # 7 ------------------------------------------------------------------------------ model puanlama, analiz
    with st.expander("6. Modellerle puanlama ve değerlendirme", expanded=rated):
        job = job_status()
        if job:
            state = "⏳ Çalışıyor" if job["running"] else ("✅ Bitti" if job["ok"] else "❌ Durdu")
            st.markdown(f"**Son iş:** {job['label']} · {state} · başlangıç {job['started']} · günlük `{job['log']}`")
            st.code(job["tail"] or "(henüz çıktı yok)")
            if st.button("Yenile"):
                st.rerun()
        if not rated:
            st.caption("Önce altın setin iki puanlayıcı puanlarını yükleyin (hakem puanları da önerilir).")
        else:
            st.caption(f"Model paneli kenar çubuğundan seçilir: `{models_path}`. Gerçek modellerde model sunucuları "
                       "açık olmalıdır (Modeller sekmesinden sınayın). CPU'da tam çalışma günler sürebilir; iş arka "
                       "planda yürür, tarayıcıyı kapatabilirsiniz.")
            c1, c2 = st.columns(2)
            limit = c1.number_input("Pilot: soru başına en fazla N yanıt (0 = tümü)", 0, 1000, 5)
            real_emb = c2.checkbox("Gerçek gömme modelleri (ilk seferde ~10 GB indirir)", value=False)
            busy = bool(job and job["running"])
            if st.button("Puanlamayı başlat (altın set: tüm koşullar → değerlendirme → yanlılık verisi)",
                         type="primary", disabled=busy):
                abl = ["run-ablation", "--models", models_path, "-y", "--no-evaluate"]
                if limit:
                    abl += ["--limit", str(limit)]
                if not real_emb:
                    abl.append("--offline-embedding-demo")
                clear_old_results()
                start_job([abl, ["evaluate"], ["export-bias-data"]],
                          f"Ablasyon{' (pilot, ' + str(limit) + ' yanıt/soru)' if limit else ''}")
                time.sleep(1)
                st.rerun()
            if busy:
                st.caption("Bir iş çalışırken yenisi başlatılamaz.")
            st.caption("Bittiğinde sonuçlar **Sonuçlar** sekmesinde görünür. Kararlılık ölçümü farklı bir günde: "
                       "`scoring score --condition stability --replicate 2`.")
