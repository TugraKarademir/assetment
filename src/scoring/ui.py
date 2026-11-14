"""Tarayıcı arayüzü (Streamlit):  uv run scoring ui

Sekmeler: Yanıt dene · Sonuçlar · Modeller · Sentetik deneme
Arayüz yalnızca 127.0.0.1'e bağlanır; uzaktan erişim için SSH tüneli kullanın (docs/arayuz.md).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
load_dotenv()

from scoring.config import load_experiment, load_items  # noqa: E402

st.set_page_config(page_title="Katmanlı puanlama", page_icon="📝", layout="wide")

PANEL_LABELS = {
    "models.mock.yaml": "Sahte modeller (kurulum gerektirmez; puanlar anlamlı değildir)",
    "models.yaml": "Yerel modeller — 64 çekirdekli CPU sunucusu (varsayılan)",
    "models.cpu.3servers.yaml": "Yerel modeller — 3 CPU sunucusu",
    "models.cpu.single.yaml": "Yerel modeller — tek CPU sunucusu (Ollama)",
    "models.gpu.vllm.yaml": "Yerel modeller — GPU (vLLM)",
    "models.gpu.ollama.yaml": "Yerel modeller — GPU (Ollama)",
    "models.api.yaml": "Ticari API modelleri (veri kurum dışına çıkar)",
}


@st.cache_data
def _bank():
    return load_items()


def _panels() -> dict[str, str]:
    files = sorted(Path("config").glob("models*.yaml"), key=lambda p: list(PANEL_LABELS).index(p.name)
                   if p.name in PANEL_LABELS else 99)
    return {PANEL_LABELS.get(p.name, p.name): str(p) for p in files}


def _panel_info(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- kenar çubuğu
with st.sidebar:
    st.header("Ayarlar")
    panels = _panels()
    label = st.selectbox("Model paneli", list(panels), index=0)
    models_path = panels[label]
    info = _panel_info(models_path)
    st.caption("Puanlayıcılar: " + ", ".join(info["models"][k]["model"] for k in info["scorers"]))
    st.caption("Birleştirici: " + info["models"][info["aggregator"]]["model"])
    is_mock = models_path.endswith("models.mock.yaml")
    if is_mock:
        st.warning("Sahte modeller gerçek dil modeli değildir. Yalnızca arayüzü ve akışı denemek içindir.")
    elif models_path.endswith("models.api.yaml"):
        st.error("Bu panel metni kurum dışındaki API'lere gönderir. Gerçek öğrenci verisiyle kullanmayın.")
    exp = load_experiment()
    st.caption(f"Gerekçe kipi: {exp.prompt_options.get('rationale_style', 'standard')}")
    st.divider()
    st.caption("Her deneme kayda geçer: `logs/<çalıştırma>/calls.jsonl`. Denemeler araştırma verisine yazılmaz.")

st.title("Katmanlı çok modelli puanlama")
tab_try, tab_results, tab_models, tab_demo = st.tabs(["Yanıt dene", "Sonuçlar", "Modeller", "Sentetik deneme"])

# ----------------------------------------------------------------------------- Yanıt dene
with tab_try:
    bank = _bank()
    left, right = st.columns([1, 1])
    with left:
        item_id = st.selectbox("Soru", bank.ids, format_func=lambda i: f"{i} — {bank[i].question[:70]}…")
        item = bank[item_id]
        st.markdown(f"**{item.item_id}** ({item.bloom} düzey): {item.question}")
        examples = {"(boş)": ""} | {f"Örnek yanıt — çapa {a.anchor_id} (puanlar {list(a.scores.values())})": a.text
                                    for a in item.anchors}
        ex = st.selectbox("Hazır örnek yükle", list(examples))
        text = st.text_area("Öğrenci yanıtı", value=examples[ex], height=220,
                            placeholder="Yanıtı buraya yapıştırın. Ad, numara, e-posta gibi kişisel veriler "
                                        "gönderilmeden önce otomatik maskelenir.")
        layers = st.radio("Katmanlar", [3, 2, 1], horizontal=True,
                          format_func=lambda v: {1: "Yalnızca Katman 1", 2: "Katman 1–2", 3: "Katman 1–3 (tam)"}[v])
        if not is_mock:
            st.caption("Gerçek modellerde tüm model sunucuları açık olmalıdır (bkz. Modeller sekmesi). "
                       "CPU'da tek yanıt birkaç dakika sürebilir.")
        go = st.button("Puanla", type="primary", disabled=not text.strip())
    with right:
        with st.expander("Rubrik", expanded=False):
            for c in item.criteria:
                st.markdown(f"**{c.criterion_id} – {c.name}** ({c.score_min}–{c.score_max}): {c.description}")
                st.table(pd.DataFrame({"Puan": list(c.levels), "Tanımlayıcı": list(c.levels.values())}))
        if item.reference_answer:
            with st.expander("Referans yanıt"):
                st.write(item.reference_answer)

    if go:
        from scoring.try_one import score_single
        with st.spinner("Puanlanıyor…"):
            try:
                st.session_state["trial"] = score_single(item_id, text, models_path, max_layer=layers)
            except Exception as e:  # sunucu kapalı, yapılandırma hatası vb.
                st.session_state.pop("trial", None)
                st.error(f"Puanlama başarısız: {type(e).__name__}: {e}")

    res = st.session_state.get("trial")
    if res is not None and res.item_id == item_id:
        st.divider()
        if res.n_masked:
            st.info(f"{res.n_masked} kişisel veri öğesi maskelendi. Modellere giden metin:\n\n> {res.masked_text}")
        for e in res.errors:
            st.error(e)
        st.subheader("Puanlar")
        st.dataframe(res.summary, hide_index=True, width="stretch")
        st.caption("K1: bağımsız puanlama · K2: diğer modelleri gördükten sonra revizyon · Ortalama/Ortanca: son "
                   "katmandaki model puanlarından · Öğrenilmiş ağırlıklar yalnızca altın set üzerinde hesaplanır, "
                   "tek yanıtta gösterilmez.")
        st.subheader("Gerekçeler")
        names = {1: "Katman 1 — bağımsız puanlama", 2: "Katman 2 — revizyon", 3: "Katman 3 — birleştirici"}
        for layer in sorted(res.rows.layer.unique()):
            with st.expander(names[int(layer)], expanded=int(layer) == 1):
                d = res.rows[res.rows.layer == layer]
                for mk, g in d.groupby("model_key", sort=False):
                    st.markdown(f"**{mk}**")
                    show = g[["criterion_id", "score", "rationale", "rubric_evidence", "evidence_verbatim"]].rename(
                        columns={"criterion_id": "Ölçüt", "score": "Puan", "rationale": "Gerekçe",
                                 "rubric_evidence": "Kanıt alıntısı", "evidence_verbatim": "Alıntı yanıtta var mı"})
                    st.dataframe(show, hide_index=True, width="stretch")
        stats = res.notes.get("engine_stats", {})
        st.caption(f"Çalıştırma: `{res.run_id}` · yanıt kodu: `{res.response_id}` · model çağrısı: "
                   f"{stats.get('api_calls', 0)} · önbellekten: {stats.get('cache_hits', 0)} · "
                   f"kayıt: `logs/{res.run_id}/calls.jsonl`")

# ----------------------------------------------------------------------------- Sonuçlar
with tab_results:
    rdir = exp.path("results_dir")
    tables = [("summary_total_pooled", "Ana tablo — toplam puan, tüm sorular (QWK, ICC, uyum, MAE, SMD; %95 GA)"),
              ("qwk_total_by_item", "Soru bazında QWK (toplam puan)"),
              ("wxb_pass_fail_total", "Williamson, Xi ve Breyer (2012) ölçütleri — geçti/kaldı"),
              ("paired_differences", "Koşullar arası QWK farkı (eşleştirilmiş bootstrap)"),
              ("weights_variability", "Öğrenilmiş ağırlıklar ve katlara göre değişimi"),
              ("stability", "Kararlılık — aynı modelin iki puanlaması"),
              ("rationale_quality", "Gerekçe kalitesi — kanıt alıntıları ve revizyon oranı"),
              ("coverage", "Kapsam — puanlanabilen yanıt oranı")]
    found = [(n, t) for n, t in tables if (rdir / f"{n}.csv").exists()]
    if not found:
        st.info("Henüz sonuç yok. 'Sentetik deneme' sekmesinden bir deneme çalıştırabilir ya da komut satırında "
                "`uv run scoring evaluate` kullanabilirsiniz.")
    else:
        readme = rdir / "README.md"
        if readme.exists() and "sentetik" in readme.read_text(encoding="utf-8").lower():
            st.warning("Bu klasördeki sonuçlar sentetik veri ve sahte modellerle üretilmiş ÖRNEK çıktıdır; "
                       "bilimsel bulgu değildir.")
        for name, title in found:
            with st.expander(title, expanded=name == "summary_total_pooled"):
                df = pd.read_csv(rdir / f"{name}.csv")
                st.dataframe(df, hide_index=True, width="stretch")
                st.download_button("CSV indir", (rdir / f"{name}.csv").read_bytes(), f"{name}.csv", key=f"dl_{name}")
        figs = sorted((rdir / "figures").glob("bland_altman_*.png"))
        if figs:
            st.subheader("Bland–Altman grafikleri")
            pick = st.selectbox("Koşul", figs, format_func=lambda p: p.stem.replace("bland_altman_", ""))
            st.image(str(pick), width=720)

# ----------------------------------------------------------------------------- Modeller
with tab_models:
    st.markdown("Seçili paneldeki her model için **bağlantı**, **geçerli JSON** ve **bağlam kesilmesi** testi.")
    rows = [{"Rol": "puanlayıcı" if k in info["scorers"] else "birleştirici", "Anahtar": k, "Model": m["model"],
             "Aile": m.get("family", ""), "Adres değişkeni": m.get("base_url_env", "—"),
             "Adres": os.environ.get(m.get("base_url_env") or "", "tanımlı değil") if m.get("base_url_env") else "—",
             "Sürüm/özet": str(m.get("model_revision", ""))[:22]}
            for k, m in info["models"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not is_mock:
        st.caption("64 çekirdekli sunucuda tek yanıt denemesi için dört modeli birlikte başlatın: "
                   "`bash scripts/cpu64/start_all_for_ui.sh` · durdurmak için: `bash scripts/cpu64/stop_servers.sh all`")
    if st.button("Bağlantıyı sına"):
        with st.spinner("Modeller sınanıyor…"):
            p = subprocess.run([sys.executable, "-m", "scoring.cli", "check-models", "--models", models_path],
                               capture_output=True, text=True, timeout=3600)
        st.code((p.stdout + p.stderr).strip() or "(çıktı yok)")

# ----------------------------------------------------------------------------- Sentetik deneme
with tab_demo:
    st.markdown(
        "Sentetik veriyle **uçtan uca** deneme: sentetik sınav dışa aktarımı → anonimleştirme → altın set → "
        "8 ablasyon koşulu → kararlılık → değerlendirme. Sahte modellerle yaklaşık bir dakika sürer.\n\n"
        "**Dikkat:** `data/` altındaki mevcut işlenmiş veriyi ve `results/` tablolarını sentetik olanlarla "
        "değiştirir. Gerçek veriyle çalışmaya başladıktan sonra kullanmayın.")
    real = Path("data/raw/moodle_export.csv").exists() and not Path("data/synthetic/latent_truth.csv").exists()
    if real:
        st.error("`data/raw/moodle_export.csv` sentetik görünmüyor. Gerçek verinin üzerine yazmamak için bu sekme "
                 "kapatıldı.")
    confirm = st.checkbox("Mevcut işlenmiş verinin ve sonuçların değişeceğini anladım", disabled=real)
    if st.button("Sentetik denemeyi çalıştır", disabled=real or not confirm):
        args = [sys.executable, "-m", "scoring.cli", "demo"]
        if Path("data/derived/embedding_cache").exists():
            args.append("--real-embeddings")
        with st.status("Çalışıyor…", expanded=True) as status:
            box = st.empty()
            lines: list[str] = []
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONUTF8="1"))
            for ln in proc.stdout:
                if ln.strip() and not ln.startswith("|") and "it/s]" not in ln:
                    lines.append(ln.rstrip())
                    box.code("\n".join(lines[-18:]))
            code = proc.wait()
            status.update(label="Tamamlandı" if code == 0 else f"Hata (çıkış kodu {code})",
                          state="complete" if code == 0 else "error")
        if code == 0:
            st.success("Bitti. Sonuçlar 'Sonuçlar' sekmesinde.")
