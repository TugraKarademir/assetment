"""Komut satırı arayüzü:  uv run scoring --help"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from dotenv import load_dotenv

from .config import load_experiment, load_items, load_models

load_dotenv()
app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False,
                  help="Katmanlı çok modelli puanlama çerçevesi")

ModelsOpt = typer.Option("config/models.yaml", "--models", help="Model yapılandırma dosyası")


@app.command("gen-key")
def gen_key():
    """Eşleme dosyası için yeni bir Fernet anahtarı üretir (.env > MAPPING_KEY)."""
    from .anonymize import generate_key
    typer.echo(f"MAPPING_KEY={generate_key()}")
    typer.echo("Bu satırı .env dosyasına ekleyin; anahtarı kaybederseniz eşleme tablosu açılamaz.", err=True)


@app.command()
def anonymize(export: Optional[Path] = typer.Option(None, help="Moodle dışa aktarımı (CSV/XLSX)"),
              columns: Path = typer.Option("config/moodle_columns.yaml")):
    """Moodle dışa aktarımını okur, kimlikleri koda çevirir, metin içi kişisel verileri maskeler."""
    from .anonymize import anonymize_records
    from .moodle_io import load_column_map, read_moodle_export
    exp = load_experiment()
    export = export or exp.path("raw_export")
    records = read_moodle_export(export, load_column_map(columns))
    df = anonymize_records(records, exp.path("mapping"), exp.path("responses"),
                           exp.path("pii_report_private"), exp.path("pii_summary"))
    typer.echo(f"{df.student_code.nunique()} öğrenci, {len(df)} yanıt anonimleştirildi -> {exp.path('responses')}")
    typer.echo(f"Maskelenen öğe: {int(df.n_masked.sum())} ({(df.n_masked > 0).sum()} yanıtta); "
               f"maskelenmeyip işaretlenen: {int(df.n_flagged_unmasked.sum())}")
    typer.echo(f"Gizli ayrıntılı rapor: {exp.path('pii_report_private')}  |  Özet: {exp.path('pii_summary')}")


@app.command("sample-gold")
def sample_gold_cmd(per_item: Optional[int] = typer.Option(None, help="Soru başına altın set büyüklüğü"),
                    synthetic: bool = typer.Option(False, help="Sentetik deneme boyutunu kullan (experiment.yaml)"),
                    labelstudio: bool = typer.Option(True, help="Label Studio JSON'u da yaz")):
    """Altın seti katmanlı seçkisiz örnekler; katları ve puanlayıcı dosyalarını yazar."""
    from .data import load_human_scores, load_responses, official_scores
    from .sampling import assign_folds, sample_gold, write_labelstudio, write_rating_sheet
    exp, bank = load_experiment(), load_items()
    responses = load_responses(exp.path("responses"))
    official = official_scores(load_human_scores(exp.path("human_scores")))
    n = per_item or exp.gold["synthetic_per_item" if synthetic else "per_item"]
    seed = exp.seeds["gold_sampling"]
    anchor_sources = {a.source_response_id for it in bank.items for a in it.anchors if a.source_response_id}
    gold = sample_gold(responses, official, bank, n, exp.gold["strata_bins"], seed, anchor_sources)
    folds = assign_folds(gold, exp.gold["n_folds"], exp.seeds["folds"])
    gold.assign(seed=seed).to_csv(exp.path("gold_sample"), index=False)
    folds.to_csv(exp.path("gold_folds"), index=False)
    write_rating_sheet(gold, responses, bank, exp.path("gold_excel"), seed)
    msg = f"Altın set: {len(gold)} yanıt ({gold.groupby('item_id').size().to_dict()}), tohum={seed}"
    if labelstudio:
        cfg = write_labelstudio(gold, responses, bank, exp.path("gold_labelstudio"), seed)
        msg += f"\nLabel Studio: {exp.path('gold_labelstudio')} (+ {cfg.name})"
    typer.echo(msg + f"\nPuanlayıcı dosyası: {exp.path('gold_excel')}\nKatlar: {exp.path('gold_folds')}")


@app.command("check-leakage")
def check_leakage_cmd():
    """Çapa yanıtların altın setten gelmediğini denetler (ihlalde çıkış kodu 1)."""
    from .data import load_responses
    from .leakage import LeakageError, check_leakage
    exp, bank = load_experiment(), load_items()
    gold = pd.read_csv(exp.path("gold_sample"), dtype=str)
    try:
        for n in check_leakage(bank, load_responses(exp.path("responses")), set(gold.response_id)):
            typer.echo(n)
        typer.echo("Sızıntı yok.")
    except LeakageError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)


def _prepare(subset: str, models_path: Path, limit: Optional[int] = None):
    """Ortak hazırlık: yapılandırma, yanıt alt kümesi ve (her zaman) sızıntı denetimi."""
    from .data import load_responses
    from .leakage import check_leakage
    exp, bank, models = load_experiment(), load_items(), load_models(models_path)
    responses = load_responses(exp.path("responses"))
    gold_path = exp.path("gold_sample")
    gold_ids = set(pd.read_csv(gold_path, dtype=str).response_id) if gold_path.exists() else set()
    check_leakage(bank, responses, gold_ids)
    if subset == "gold":
        if not gold_ids:
            raise typer.BadParameter("Altın set yok: önce `scoring sample-gold` çalıştırın.")
        responses = responses[responses.response_id.isin(gold_ids)]
    # Aynı sorunun yanıtları art arda: rubrik + çapalardan oluşan ortak önek sunucuda önbellekten okunur (prefix caching)
    responses = responses[~responses.is_empty].sort_values(["item_id", "response_id"])
    if limit:
        responses = responses.groupby("item_id").head(limit)
    return exp, bank, models, responses


def _confirm_cost(est: pd.DataFrame, yes: bool) -> None:
    from .utils import df_to_markdown
    typer.echo(df_to_markdown(est, ".2f"))
    total = est.est_cost_usd.sum()
    typer.echo(f"TAHMİNİ TOPLAM MALİYET: ${total:,.2f} (çağrı: {int(est.calls.sum())}, önbellekte: "
               f"{int(est.cached.sum())}; Katman 2/3 tahmini kabadır)")
    if not yes and not typer.confirm("Devam edilsin mi?", default=False):
        raise typer.Exit(1)


@app.command("estimate-cost")
def estimate_cost_cmd(condition: str = typer.Option("ablation"), subset: str = typer.Option("gold"),
                      models: Path = ModelsOpt, replicate: int = 1):
    """Bir çalıştırmanın çağrı sayısını ve maliyetini, istemleri oluşturarak tahmin eder."""
    from .pipeline import CONDITION_PLANS, estimate_cost
    exp, bank, mcfg, responses = _prepare(subset, models)
    est = estimate_cost(responses, bank, mcfg, exp, CONDITION_PLANS[condition], replicate)
    _confirm_cost(est, yes=True)


@app.command()
def score(condition: str = typer.Option("full", help="full | panel_vote | single_anchored | ablation | stability ..."),
          subset: str = typer.Option("gold", help="gold | all"),
          models: Path = ModelsOpt,
          replicate: int = typer.Option(1, help="Kararlılık için 2 (önbellek ayrı tutulur)"),
          yes: bool = typer.Option(False, "--yes", "-y", help="Maliyet onayını atla"),
          no_batch: bool = typer.Option(False, help="Toplu (batch) API kullanma"),
          limit: Optional[int] = typer.Option(None, help="Soru başına en fazla N yanıt (deneme için)"),
          sequential_models: bool = typer.Option(False, help="Modelleri aynı anda değil sırayla çağır (tek GPU / Ollama)"),
          only_models: Optional[str] = typer.Option(None, help="Virgülle ayrılmış model anahtarları: yalnızca bunlar "
                                                    "çağrılır, diğerleri yalnızca önbellekten okunur (tek GPU / vLLM)"),
          max_layer: int = typer.Option(3, help="Bu katmandan sonrasını çalıştırma (1, 2 ya da 3)")):
    """LLM katmanlarını çalıştırır ve ham puanları depoya ekler."""
    from .manifest import new_run_id, write_manifest
    from .pipeline import CONDITION_PLANS, estimate_cost, run_pipeline, store_raw_scores
    if condition not in CONDITION_PLANS:
        raise typer.BadParameter(f"Bilinmeyen koşul: {condition}. Seçenekler: {list(CONDITION_PLANS)}")
    exp, bank, mcfg, responses = _prepare(subset, models, limit)
    plan = CONDITION_PLANS[condition]
    _confirm_cost(estimate_cost(responses, bank, mcfg, exp, plan, replicate), yes)
    run_id = new_run_id(f"{condition}_r{replicate}")
    write_manifest(run_id, exp.path("logs_dir"), exp.path("results_dir"),
                   ["config/items.yaml", str(models), "config/experiment.yaml", "config/moodle_columns.yaml"],
                   exp.seeds, {"condition": condition, "subset": subset, "replicate": replicate,
                               "n_responses": len(responses), "models": mcfg.model_dump(mode="json"),
                               "plan": plan.__dict__})
    only = set(only_models.split(",")) if only_models else None
    if only and not only <= set(mcfg.models):
        raise typer.BadParameter(f"Bilinmeyen model anahtarı: {only - set(mcfg.models)}")
    new, notes = asyncio.run(run_pipeline(responses, bank, mcfg, exp, plan, replicate, run_id, condition,
                                          use_batch=not no_batch, sequential_models=sequential_models,
                                          only_models=only, max_layer=max_layer))
    store_raw_scores(exp.path("raw_scores"), new)
    typer.echo(f"Çalıştırma {run_id} tamamlandı. Kayıt: logs/{run_id}/calls.jsonl")
    for k, v in notes.items():
        typer.echo(f"  {k}: {v}")


@app.command("check-models")
def check_models_cmd(models: Path = ModelsOpt):
    """Her modelin uç noktasına ulaşılabildiğini ve geçerli JSON döndürdüğünü küçük bir istekle sınar."""
    from .providers import LLMRequest, make_provider
    mcfg = load_models(models)

    async def probe(key):
        spec = mcfg.spec(key)
        try:
            prov = make_provider(spec)
            served = None
            if spec.provider == "openai_compat":
                served = [m.id async for m in prov.client.models.list()]
            res = await prov.complete(LLMRequest(key, "Yalnızca JSON döndür.",
                                                 [{"role": "user", "content": 'Şunu aynen döndür: {"ok": true}'}]))
            status = "HATA: " + res.error if res.error else ("JSON tamam" if '"ok"' in res.text else f"beklenmeyen: {res.text[:80]}")
            # Bağlam uzunluğu testi: istemin EN BAŞINA bir kod konur, ~3.500 token dolgu eklenir.
            # Sunucu bağlamı kesiyorsa (ör. Ollama varsayılan num_ctx) kod kaybolur -> rubrik de kaybolur.
            filler = " ".join(["Bu cümle bağlam uzunluğu testi için eklenmiş dolgu metnidir."] * 200)
            long = await prov.complete(LLMRequest(key, "Yalnızca JSON döndür.", [{"role": "user", "content":
                   f"GİZLİ KOD: KESTANE-7351.\n{filler}\nMetnin EN BAŞINDA verilen gizli kodu "
                   '{"kod": "<kod>"} biçiminde döndür.'}]))
            ctx_ok = "7351" in (long.text or "")
            status += f" | uzun istem ({long.input_tokens} token): " + ("bağlam TAMAM" if ctx_ok else
                      "BAĞLAM KESİLİYOR olabilir — sunucuda bağlam uzunluğunu ≥ 8192 yapın")
            return key, spec.model, res.model_version_returned, served, status, round(res.latency_s, 2)
        except Exception as e:
            return key, spec.model, None, None, f"HATA: {type(e).__name__}: {str(e)[:150]}", None

    async def run_all():
        return [await probe(k) for k in [*mcfg.scorers, mcfg.aggregator]]

    for key, model, returned, served, status, lat in asyncio.run(run_all()):
        typer.echo(f"[{key}] {model} -> {status} (dönen sürüm: {returned}, gecikme: {lat}s)")
        if served is not None and model not in served:
            typer.echo(f"   UYARI: sunucuda sunulan modeller: {served}")


@app.command()
def benchmark(models: Path = ModelsOpt,
              n: int = typer.Option(2, help="Soru başına ölçüm yanıtı sayısı (model başına çağrı = n × soru sayısı)"),
              n_gold: int = typer.Option(1200, help="Planlanan altın set büyüklüğü (gerçek çalışma: 4 × 300)"),
              n_all: int = typer.Option(3200, help="Planlanan toplam yanıt sayısı"),
              condition: str = typer.Option("ablation", help="ablation | ablation_core")):
    """Her modelin CPU sunucusundaki hızını ölçer ve tüm çalışmanın süresini tahmin eder."""
    from .benchmark import measure, project, workload
    from .engine import CallEngine
    from .layers import PromptRenderer
    from .manifest import new_run_id, write_manifest
    from .utils import df_to_markdown, write_table
    exp, bank, mcfg, responses = _prepare("all", models)
    sample = responses.groupby("item_id").head(n)
    run_id = new_run_id("benchmark")
    write_manifest(run_id, exp.path("logs_dir"), exp.path("results_dir"),
                   ["config/items.yaml", str(models), "config/experiment.yaml"], exp.seeds,
                   {"condition": "benchmark", "n_per_item": n, "models": mcfg.model_dump(mode="json")})
    engine = CallEngine(mcfg, run_id, exp.path("cache"), exp.path("logs_dir"))
    renderer = PromptRenderer(rationale_style=exp.prompt_options.get("rationale_style", "standard"))
    speed = asyncio.run(measure(sample, bank, mcfg, engine, renderer, run_id))
    typer.echo("ÖLÇÜLEN HIZ (gerçek istemler, Katman 1):\n" + df_to_markdown(speed, ".1f"))
    if (speed.valid < speed.calls).any():
        typer.echo("UYARI: bazı ölçüm çağrıları geçersiz/başarısız (first_error sütunu). Önce `check-models` çalıştırın.",
                   err=True)
    layer, phase = project(workload(n_gold, n_all, mcfg.scorers, mcfg.aggregator, condition), speed)
    typer.echo("KATMAN BAŞINA DUVAR SAATİ (puanlayıcılar ayrı sunucularda paralel):\n" + df_to_markdown(layer, ".1f"))
    typer.echo("TAHMİNİ TOPLAM SÜRE:\n" + df_to_markdown(phase, ".1f"))
    out = exp.path("results_dir") / "benchmark"
    write_table(speed, out / "speed")
    write_table(layer, out / "projection_by_layer")
    write_table(phase, out / "projection_total")
    typer.echo(f"Not: K2/K3 istemleri K1'den ~%30 uzundur; tahmin K1 hızına dayanır. Kayıt: logs/{run_id}/")


def _gold_context():
    from .data import gold_consensus, load_human_scores, load_responses
    exp, bank = load_experiment(), load_items()
    responses = load_responses(exp.path("responses"))
    folds = pd.read_csv(exp.path("gold_folds"), dtype={"response_id": str, "student_code": str})
    consensus = gold_consensus(load_human_scores(exp.path("human_scores")), exp.gold["consensus"],
                               exp.aggregation["rounding"])
    consensus = consensus[consensus.response_id.isin(folds.response_id)]
    return exp, bank, responses, folds, consensus


@app.command("embed-baseline")
def embed_baseline_cmd(offline_demo: bool = typer.Option(False, help="HuggingFace erişimi yoksa TF-IDF DEMO kodlayıcı"),
                       models_subset: Optional[str] = typer.Option(None, help="Virgülle ayrılmış model adları (alt küme)")):
    """Gömme tabanlı karşılaştırma koşulu (altın set, aynı katlar)."""
    from .data import criteria_frame
    from .embedding_baseline import (SentenceTransformerEncoder, TfidfDemoEncoder, cv_embedding_scores,
                                     log_embedding_run, similarity_features)
    from .leakage import check_leakage
    from .manifest import new_run_id, write_manifest
    exp, bank, responses, folds, consensus = _gold_context()
    check_leakage(bank, responses, set(folds.response_id))
    gold = responses[responses.response_id.isin(folds.response_id)]
    emb = exp.embedding
    if offline_demo:
        corpus = list(responses.text) + [a.text for it in bank.items for a in it.anchors] + \
                 [it.reference_answer or "" for it in bank.items]
        encoders, condition = [TfidfDemoEncoder(corpus=corpus)], "embedding_tfidf_demo"
    else:
        specs = emb["models"]
        if models_subset:
            keep = set(models_subset.split(","))
            specs = [m for m in specs if m["name"] in keep]
        encoders = [SentenceTransformerEncoder(m["name"], m.get("query_prefix", ""), m.get("passage_prefix", ""),
                                               cache_dir="data/derived/embedding_cache",
                                               forbidden=emb.get("forbidden_patterns"), revision=m.get("revision"))
                    for m in specs]
        condition = "embedding"
    run_id = new_run_id(condition)
    write_manifest(run_id, exp.path("logs_dir"), exp.path("results_dir"),
                   ["config/items.yaml", "config/experiment.yaml"], exp.seeds,
                   {"condition": condition, "encoders": [{"name": e.name, "revision": getattr(e, "revision", None)}
                                                          for e in encoders]})
    feats = similarity_features(gold, bank, encoders, emb.get("softmax_temperature", 0.05))
    y = consensus[["response_id", "criterion_id", "consensus"]].rename(columns={"consensus": "y"})
    preds, coefs = cv_embedding_scores(feats, y, folds, criteria_frame(bank)[["item_id", "criterion_id", "score_min", "score_max"]],
                                       level=emb.get("ordinal_level", "item"), l2=emb.get("ordinal_l2", 1.0))
    preds = log_embedding_run(run_id, exp.path("logs_dir"), preds, [e.name for e in encoders], condition)
    preds.assign(condition=condition).to_csv("data/derived/embedding_preds.csv", index=False)
    coefs.to_csv(exp.path("results_dir") / "embedding_ordinal_coefficients.csv", index=False)
    typer.echo(f"{condition}: {preds.pred.notna().sum()} / {len(preds)} ölçüt puanı tahmin edildi (run {run_id})")


@app.command("build-conditions")
def build_conditions_cmd(models: Path = ModelsOpt, replicate: int = 1):
    """Ham puanlardan tüm ablasyon koşullarının puanlarını (aynı katlarla) üretir."""
    from .ablation import build_condition_scores, summarize_weights
    from .pipeline import load_raw_scores
    from .utils import write_table
    exp, bank, responses, folds, consensus = _gold_context()
    mcfg = load_models(models)
    raw = load_raw_scores(exp.path("raw_scores"))
    emb_path = Path("data/derived/embedding_preds.csv")
    emb, emb_cond = None, "embedding"
    if emb_path.exists():
        emb = pd.read_csv(emb_path, dtype={"response_id": str, "call_id": str})
        emb_cond = emb.condition.iloc[0]
    cond, weights = build_condition_scores(raw, consensus, folds, responses, bank, mcfg.scorers, mcfg.aggregator,
                                           exp.aggregation["rounding"], exp.aggregation["weights_level"],
                                           replicate, emb, emb_cond)
    cond.to_csv(exp.path("condition_scores"), index=False)
    if not weights.empty:
        weights.to_csv(exp.path("results_dir") / "weights_by_fold.csv", index=False)
        write_table(summarize_weights(weights), exp.path("results_dir") / "weights_variability")
    typer.echo(f"{cond.condition.nunique()} koşul -> {exp.path('condition_scores')}")
    typer.echo("Koşullar: " + ", ".join(sorted(cond.condition.unique())))


@app.command("run-ablation")
def run_ablation(models: Path = ModelsOpt, yes: bool = typer.Option(False, "--yes", "-y"),
                 no_batch: bool = False, offline_embedding_demo: bool = typer.Option(False),
                 skip_embedding: bool = False, evaluate_after: bool = typer.Option(True, "--evaluate/--no-evaluate"),
                 limit: Optional[int] = None, sequential_models: bool = typer.Option(False)):
    """Tüm ablasyon koşullarını tek komutla üretir: LLM katmanları + gömme koşulu + koşul puanları (+ değerlendirme)."""
    score(condition="ablation", subset="gold", models=models, replicate=1, yes=yes, no_batch=no_batch, limit=limit,
          sequential_models=sequential_models, only_models=None, max_layer=3)
    if not skip_embedding:
        embed_baseline_cmd(offline_demo=offline_embedding_demo, models_subset=None)
    build_conditions_cmd(models=models, replicate=1)
    if evaluate_after:
        evaluate_cmd(bootstrap_reps=None)


@app.command("evaluate")
def evaluate_cmd(bootstrap_reps: Optional[int] = typer.Option(None, help="Varsayılan: experiment.yaml (2000)")):
    """Tüm koşullar için uyum metrikleri, GA'lar, W-X-B tablosu, eşleştirilmiş farklar ve grafikler -> results/."""
    from .engine import load_call_ids
    from .evaluate import enforce_logged, evaluate
    from .pipeline import load_raw_scores
    exp, bank, responses, folds, consensus = _gold_context()
    ev = exp.evaluation
    cond = pd.read_csv(exp.path("condition_scores"), dtype={"response_id": str, "call_ids": str})
    cond, excluded = enforce_logged(cond, load_call_ids(exp.path("logs_dir")))
    if len(excluded):
        typer.echo(f"UYARI: kaydı olmayan {len(excluded)} puan raporlamadan çıkarıldı (results/excluded_unlogged.csv)", err=True)
    excluded.to_csv(exp.path("results_dir") / "excluded_unlogged.csv", index=False)
    wpath = exp.path("results_dir") / "weights_by_fold.csv"
    tables = evaluate(cond, consensus, responses, bank, exp.path("results_dir"),
                      bootstrap_reps or ev["bootstrap_reps"], exp.seeds["bootstrap"], ev["ci"], ev["reference"],
                      ev["thresholds"], ev["paired_comparisons"], raw=load_raw_scores(exp.path("raw_scores")),
                      manifests_dir=exp.path("results_dir") / "manifests",
                      weights=pd.read_csv(wpath) if wpath.exists() else None)
    from .utils import df_to_markdown
    typer.echo(df_to_markdown(tables["summary_total_pooled"]))
    typer.echo(f"Tablolar ve grafikler: {exp.path('results_dir')}/")


@app.command("export-bias-data")
def export_bias_data_cmd():
    """R'daki karma model için düz yanlılık veri dosyası (+ metin öznitelikleri)."""
    from .evaluate import export_bias_data
    from .text_features import SpellChecker, text_features
    exp, bank, responses, folds, consensus = _gold_context()
    cond = pd.read_csv(exp.path("condition_scores"), dtype={"response_id": str})
    gold = responses[responses.response_id.isin(folds.response_id)]
    checker = SpellChecker()
    feats = text_features(gold, checker)
    p1, p2 = export_bias_data(cond, consensus, responses, bank, feats, exp.path("results_dir") / "bias", checker.method)
    typer.echo(f"Yazım denetimi: {checker.method}\n-> {p1}\n-> {p2}\nÖrnek R betiği: scripts/bias_model.R")


@app.command("final-scores")
def final_scores_cmd(models: Path = ModelsOpt):
    """Tam çerçeve ile operasyonel puanlar: altın set için kat dışı (CV) tahminler, diğer yanıtlar için tüm altın
    set üzerinde öğrenilen ağırlıklar. Önce `score --condition full --subset all` çalıştırılmalıdır."""
    from .ablation import build_condition_scores
    from .aggregation import full_data_weights, round_clip_series, weighted_predict
    from .data import criteria_frame
    from .pipeline import load_raw_scores
    exp, bank, responses, folds, consensus = _gold_context()
    mcfg = load_models(models)
    raw = load_raw_scores(exp.path("raw_scores"))
    raw = raw[(raw.replicate == 1) & (raw.variant == "anchored") & (raw.layer == 2) & raw.score.notna()]
    crit = criteria_frame(bank)
    wide = (raw.pivot_table(index=["response_id", "criterion_id"], columns="model_key", values="score", aggfunc="first")
            .reset_index().merge(responses[["response_id", "item_id"]], on="response_id")
            .merge(crit, on=["item_id", "criterion_id"]))
    cols = [m for m in mcfg.scorers if m in wide]
    gw = wide[wide.response_id.isin(folds.response_id)].merge(
        consensus[["response_id", "criterion_id", "consensus"]].rename(columns={"consensus": "y"}))
    W = full_data_weights(gw, cols, exp.aggregation["weights_level"])
    level = exp.aggregation["weights_level"]
    wide["group"] = {"item": wide.item_id, "item_criterion": wide.item_id + "/" + wide.criterion_id,
                     "global": pd.Series("all", index=wide.index)}[level]
    preds = pd.Series(float("nan"), index=wide.index)
    for g, idx in wide.groupby("group").groups.items():
        w = W[W.group == g].set_index("model_key").weight.reindex(cols).to_numpy()
        preds[idx] = weighted_predict(wide.loc[idx, cols].to_numpy(), w)
    wide["score"] = round_clip_series(preds, wide.score_min, wide.score_max, exp.aggregation["rounding"])
    wide["source"] = "tüm-altın-set-ağırlıkları"
    cond, _ = build_condition_scores(load_raw_scores(exp.path("raw_scores")), consensus, folds, responses, bank,
                                     mcfg.scorers, mcfg.aggregator, exp.aggregation["rounding"], level)
    cv = cond[cond.condition == "full"].set_index(["response_id", "criterion_id"]).score
    is_gold = wide.response_id.isin(folds.response_id)
    wide.loc[is_gold, "score"] = [cv.get((r, c)) for r, c in zip(wide.response_id[is_gold], wide.criterion_id[is_gold])]
    wide.loc[is_gold, "source"] = "altın-set-kat-dışı-CV"
    out = wide[["response_id", "item_id", "criterion_id", "score", "source"]]
    out.to_csv("data/derived/final_scores.csv", index=False)
    W.to_csv(exp.path("results_dir") / "weights_full_gold.csv", index=False)
    typer.echo(f"{out.response_id.nunique()} yanıt -> data/derived/final_scores.csv")


def main():
    app()


if __name__ == "__main__":
    main()
