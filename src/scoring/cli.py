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
    responses = responses[~responses.is_empty].sort_values("response_id")
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
          limit: Optional[int] = typer.Option(None, help="Soru başına en fazla N yanıt (deneme için)")):
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
    new, notes = asyncio.run(run_pipeline(responses, bank, mcfg, exp, plan, replicate, run_id, condition,
                                          use_batch=not no_batch))
    store_raw_scores(exp.path("raw_scores"), new)
    typer.echo(f"Çalıştırma {run_id} tamamlandı. Kayıt: logs/{run_id}/calls.jsonl")
    for k, v in notes.items():
        typer.echo(f"  {k}: {v}")


def main():
    app()


if __name__ == "__main__":
    main()
