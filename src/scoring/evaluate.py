"""Değerlendirme: koşul × kapsam uyum metrikleri (bootstrap GA), insan–insan uyumu, Williamson ve ark. (2012)
ölçütleri, eşleştirilmiş koşul farkları, Bland–Altman grafikleri, kararlılık ve yanlılık veri dosyası."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .ablation import condition_sort_key
from .config import ItemBank
from .data import criteria_frame
from .metrics import METRICS, ClusterBootstrap, all_metrics, qwk
from .utils import ensure_parent, write_table

TOTAL = "TOPLAM"
ALL_CRIT = "TÜM_ÖLÇÜTLER"
POOLED = "TÜMÜ"


# ----------------------------------------------------------------------------- kayıt denetimi
def enforce_logged(cond: pd.DataFrame, logged_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kural 5: çağrı kaydı olmayan puan raporlanmaz. Kaydı eksik satırların puanı silinir ve raporlanır."""
    def ok(ids):
        if not isinstance(ids, str) or not ids:
            return False
        return all(i in logged_ids for i in ids.split(";"))
    mask = cond.score.notna() & ~cond.call_ids.map(ok)
    excluded = cond[mask][["condition", "response_id", "criterion_id"]].copy()
    cond = cond.copy()
    cond.loc[mask, "score"] = np.nan
    return cond, excluded


# ----------------------------------------------------------------------------- kapsamlar
def _scopes(df: pd.DataFrame, value_cols: list[str], bank: ItemBank) -> list[tuple[str, str, pd.DataFrame, int, int]]:
    """(soru, düzey, veri, alt, üst) listesi. Toplam yalnızca tüm ölçütleri puanlanmış yanıtlar için."""
    crit = criteria_frame(bank)
    out = []
    tot_parts = []
    for item in bank.items:
        d = df[df.item_id == item.item_id]
        for c in item.criteria:
            dc = d[d.criterion_id == c.criterion_id]
            out.append((item.item_id, c.criterion_id, dc, c.score_min, c.score_max))
        n_c = len(item.criteria)
        g = d.groupby(["response_id", "student_code", "item_id"])
        cnt = g[value_cols].count()
        t = g[value_cols].sum()
        t = t[(cnt == n_c).all(axis=1)].reset_index()
        tot_parts.append(t)
        out.append((item.item_id, TOTAL, t, item.total_min, item.total_max))
    out.append((POOLED, ALL_CRIT, df, int(crit.score_min.min()), int(crit.score_max.max())))
    allt = pd.concat(tot_parts, ignore_index=True)
    out.append((POOLED, TOTAL, allt, min(i.total_min for i in bank.items), max(i.total_max for i in bank.items)))
    return out


def _metric_rows(name, item, level, h, m, clusters, lo, hi, reps, seed, ci):
    if len(h) < 3:
        return []
    est = ClusterBootstrap(clusters, reps, seed).metrics(h, m, lo, hi, ci)
    return [{"condition": name, "item": item, "level": level, "n": len(h), "metric": k, "estimate": v[0],
             "ci_low": v[1], "ci_high": v[2]} for k, v in est.items()]


# ----------------------------------------------------------------------------- ana değerlendirme
def evaluate(cond: pd.DataFrame, consensus: pd.DataFrame, responses: pd.DataFrame, bank: ItemBank,
             out_dir: str | Path, reps: int, seed: int, ci: float, reference: str, thresholds: dict,
             pairs: list[list[str]], raw: pd.DataFrame | None = None, manifests_dir: str | Path | None = None,
             weights: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    out_dir = Path(out_dir)
    ref_col = "consensus" if reference == "consensus" else "rater1"
    stu = responses[["response_id", "student_code"]]
    human = consensus.merge(stu, on="response_id").merge(responses[["response_id", "item_id"]], on="response_id")
    conditions = sorted(cond.condition.unique(), key=condition_sort_key)
    tables: dict[str, pd.DataFrame] = {}

    # Kapsam (coverage)
    cov = (cond.groupby("condition").score.agg(n_rows="size", n_scored="count").reset_index())
    cov["coverage"] = cov.n_scored / cov.n_rows
    tables["coverage"] = cov.sort_values("condition", key=lambda s: s.map(condition_sort_key))

    # İnsan–insan
    hh_rows = []
    for item, level, d, lo, hi in _scopes(human.rename(columns={"rater1": "h1", "rater2": "h2"}), ["h1", "h2"], bank):
        hh_rows += _metric_rows("insan–insan", item, level, d.h1.to_numpy(), d.h2.to_numpy(),
                                d.student_code.to_numpy(), lo, hi, reps, seed, ci)
    hh = pd.DataFrame(hh_rows)
    tables["human_human_long"] = hh

    # Makine–insan
    rows = []
    for c in conditions:
        d = cond[cond.condition == c].merge(human[["response_id", "criterion_id", "student_code", ref_col]],
                                            on=["response_id", "criterion_id"])
        d = d[d.score.notna()].rename(columns={ref_col: "h", "score": "m"})
        for item, level, dd, lo, hi in _scopes(d, ["h", "m"], bank):
            rows += _metric_rows(c, item, level, dd.h.to_numpy(), dd.m.to_numpy(), dd.student_code.to_numpy(),
                                 lo, hi, reps, seed, ci)
    long = pd.DataFrame(rows)
    tables["agreement_long"] = pd.concat([hh, long], ignore_index=True)

    # Özet: toplam puan, tüm sorular birlikte + soru bazında QWK
    def fmt(r):
        return f"{r.estimate:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}]"
    allm = tables["agreement_long"]
    summ = []
    for c in ["insan–insan", *conditions]:
        sub = allm[(allm.condition == c) & (allm.item == POOLED) & (allm.level == TOTAL)]
        if sub.empty:
            continue
        r = {"koşul": c, "n": int(sub.n.iloc[0])}
        for k in METRICS:
            x = sub[sub.metric == k].iloc[0]
            r[k] = fmt(x) if k in ("qwk", "icc2_1", "icc3_1") else round(x.estimate, 3)
        summ.append(r)
    tables["summary_total_pooled"] = pd.DataFrame(summ)
    by_item = allm[(allm.level == TOTAL) & (allm.metric == "qwk")].pivot_table(
        index="condition", columns="item", values="estimate", aggfunc="first").reset_index()
    by_item = by_item.sort_values("condition", key=lambda s: s.map(lambda x: (-1, "") if x == "insan–insan" else condition_sort_key(x)))
    tables["qwk_total_by_item"] = by_item
    by_crit = allm[(allm.metric == "qwk") & (allm.level != TOTAL)].copy()
    by_crit["scope"] = by_crit.item + "/" + by_crit.level
    tables["qwk_by_criterion"] = by_crit.pivot_table(index="condition", columns="scope", values="estimate",
                                                     aggfunc="first").reset_index()

    # Williamson, Xi & Breyer (2012) — insan–insan düşüşü ve geçti/kaldı
    hq = hh[hh.metric == "qwk"].set_index(["item", "level"]).estimate
    wxb = []
    for (c, item, level), g in long.groupby(["condition", "item", "level"]):
        q = g[g.metric == "qwk"].estimate.iloc[0]
        s = g[g.metric == "smd"].estimate.iloc[0]
        h = hq.get((item, level), np.nan)
        drop = h - q
        ok_q, ok_d, ok_s = q >= thresholds["qwk_min"], drop <= thresholds["qwk_degradation_max"], abs(s) <= thresholds["smd_abs_max"]
        wxb.append({"condition": c, "item": item, "level": level, "qwk": q, "qwk_human_human": h,
                    "degradation": drop, "smd": s, "qwk>=.70": ok_q, "düşüş<=.10": ok_d, "|SMD|<=.15": ok_s,
                    "sonuç": "GEÇTİ" if (ok_q and ok_d and ok_s) else "KALDI"})
    w = pd.DataFrame(wxb)
    w = w.sort_values(["item", "level", "condition"], key=lambda s: s.map(condition_sort_key) if s.name == "condition" else s)
    tables["wxb_pass_fail"] = w
    tables["wxb_pass_fail_total"] = w[w.level == TOTAL].reset_index(drop=True)

    # Eşleştirilmiş farklar (toplam puan, tüm sorular; ve her soru)
    pair_rows = []
    for a, b in pairs:
        if a not in conditions or b not in conditions:
            continue
        da = cond[cond.condition == a][["response_id", "criterion_id", "score"]].rename(columns={"score": "a"})
        db = cond[cond.condition == b][["response_id", "criterion_id", "score"]].rename(columns={"score": "b"})
        d = (da.merge(db, on=["response_id", "criterion_id"])
             .merge(human[["response_id", "criterion_id", "student_code", "item_id", ref_col]], on=["response_id", "criterion_id"]))
        d = d.dropna(subset=["a", "b"]).rename(columns={ref_col: "h"})
        for item, level, dd, lo, hi in _scopes(d, ["h", "a", "b"], bank):
            if level != TOTAL or len(dd) < 3:
                continue
            bs = ClusterBootstrap(dd.student_code.to_numpy(), reps, seed)
            pt, l, u, p = bs.paired_diff(dd.h, dd.a, dd.b, "qwk", lo, hi, ci)
            pair_rows.append({"karşılaştırma": f"{a} − {b}", "item": item, "level": level, "n": len(dd),
                              "qwk_a": qwk(dd.h.astype(int), dd.a.astype(int), lo, hi),
                              "qwk_b": qwk(dd.h.astype(int), dd.b.astype(int), lo, hi),
                              "fark": pt, "ci_low": l, "ci_high": u, "p_bootstrap": p})
    tables["paired_differences"] = pd.DataFrame(pair_rows)

    # Ağırlıklar
    if weights is not None and not weights.empty:
        tables["weights_by_fold"] = weights

    # Gerekçe kalitesi: kanıt alıntısı yanıtta birebir geçiyor mu, boş mu, K2'de puan değişti mi
    if raw is not None and "evidence_verbatim" in raw:
        tables["rationale_quality"] = rationale_quality(raw)

    # Kararlılık
    if raw is not None:
        st = stability_table(raw, bank, manifests_dir)
        if st is not None:
            tables["stability"] = st

    # Yaz
    for name, t in tables.items():
        write_table(t, out_dir / name)
    bland_altman_plots(cond, human, ref_col, bank, out_dir / "figures")
    return tables


# ----------------------------------------------------------------------------- gerekçe kalitesi
def rationale_quality(raw: pd.DataFrame) -> pd.DataFrame:
    r = raw[raw.score.notna() & (raw.replicate.astype(str) == "1")].copy()
    ev = r.evidence_verbatim.map(lambda v: None if pd.isna(v) else str(v).lower() == "true")
    r["ev_given"] = ev.notna()
    r["ev_verbatim"] = ev == True  # noqa: E712
    g = r.groupby(["layer", "variant", "model_key"])
    out = g.agg(n=("score", "size"), kanıt_verilen=("ev_given", "mean"), kanıt_birebir=("ev_verbatim", "mean")).reset_index()
    out["kanıt_birebir_verilenlerde"] = out.kanıt_birebir / out.kanıt_verilen.where(out.kanıt_verilen > 0)
    ch = r[r.layer == 2].groupby(["variant", "model_key"]).changed.apply(
        lambda s: s.map(lambda v: str(v).lower() == "true").mean()).rename("k2_değiştirme_oranı").reset_index()
    return out.merge(ch.assign(layer=2), on=["layer", "variant", "model_key"], how="left")


# ----------------------------------------------------------------------------- kararlılık
def stability_table(raw: pd.DataFrame, bank: ItemBank, manifests_dir=None) -> pd.DataFrame | None:
    r = raw[(raw.layer == 1) & (raw.variant == "anchored") & raw.score.notna()]
    if r.replicate.nunique() < 2:
        return None
    crit = criteria_frame(bank)
    rows = []
    run_dates = {}
    if manifests_dir and Path(manifests_dir).exists():
        for p in Path(manifests_dir).glob("*.json"):
            m = json.loads(p.read_text(encoding="utf-8"))
            run_dates[m["run_id"]] = m["created_at_utc"][:10]
    for mk, g in r.groupby("model_key"):
        w = g.pivot_table(index=["response_id", "item_id", "criterion_id"], columns="replicate", values="score",
                          aggfunc="first").dropna()
        if w.shape[1] < 2 or w.empty:
            continue
        w = w.reset_index().merge(crit[["item_id", "criterion_id", "score_min", "score_max"]])
        r1, r2 = w.columns[3], w.columns[4]
        tot = w.groupby("response_id")[[r1, r2]].sum()
        days = sorted({run_dates.get(x, "?") for x in g.run_id.unique()})
        rows.append({"model_key": mk, "n_criterion_scores": len(w),
                     "qwk_criteria": qwk(w[r1].astype(int), w[r2].astype(int), int(w.score_min.min()), int(w.score_max.max())),
                     "exact_criteria": float((w[r1] == w[r2]).mean()),
                     "qwk_total": qwk(tot[r1].astype(int), tot[r2].astype(int)),
                     "exact_total": float((tot[r1] == tot[r2]).mean()),
                     "icc3_1_total": all_metrics(tot[r1], tot[r2])["icc3_1"],
                     "run_dates": ", ".join(days),
                     "farklı_günler": len([d for d in days if d != "?"]) > 1})
    return pd.DataFrame(rows) if rows else None


# ----------------------------------------------------------------------------- Bland–Altman
def bland_altman_plots(cond: pd.DataFrame, human: pd.DataFrame, ref_col: str, bank: ItemBank, out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out_dir.mkdir(parents=True, exist_ok=True)
    n_crit = {it.item_id: len(it.criteria) for it in bank.items}
    for c in sorted(cond.condition.unique(), key=condition_sort_key):
        d = cond[cond.condition == c].merge(human[["response_id", "criterion_id", "item_id", ref_col]],
                                            on=["response_id", "criterion_id", "item_id"]).dropna(subset=["score"])
        g = d.groupby(["response_id", "item_id"])
        t = g.agg(m=("score", "sum"), h=(ref_col, "sum"), k=("score", "count")).reset_index()
        t = t[t.k == t.item_id.map(n_crit)]
        if len(t) < 3:
            continue
        mean, diff = (t.m + t.h) / 2, t.m - t.h
        md, sd = diff.mean(), diff.std(ddof=1)
        fig, ax = plt.subplots(figsize=(6, 4.2))
        rng = np.random.default_rng(0)
        ax.scatter(mean + rng.uniform(-0.12, 0.12, len(t)), diff + rng.uniform(-0.12, 0.12, len(t)),
                   s=14, alpha=0.55, color="#3b6ea8", edgecolors="none")
        for y, ls, lab in ((md, "-", f"ortalama fark = {md:.2f}"), (md + 1.96 * sd, "--", f"+1,96 SS = {md + 1.96 * sd:.2f}"),
                           (md - 1.96 * sd, "--", f"−1,96 SS = {md - 1.96 * sd:.2f}")):
            ax.axhline(y, ls=ls, color="#555555", lw=1)
            ax.text(mean.max(), y, " " + lab, va="bottom", ha="right", fontsize=8,
                    color="#333333")
        ax.axhline(0, color="#bbbbbb", lw=0.8, zorder=0)
        ax.set_xlabel("İnsan ve makine toplam puanlarının ortalaması")
        ax.set_ylabel("Makine − insan (toplam puan)")
        ax.set_title(f"Bland–Altman: {c} (n={len(t)})", fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        safe = c.replace(":", "_").replace("/", "_")
        for ext in ("png", "svg"):
            fig.savefig(out_dir / f"bland_altman_{safe}.{ext}", dpi=150)
        plt.close(fig)


# ----------------------------------------------------------------------------- yanlılık verisi
def r_safe(name: str) -> str:
    """R'de tırnaksız kullanılabilir sütun adı (ör. single_anchored:gpt -> single_anchored__gpt)."""
    import re
    return re.sub(r"[^0-9A-Za-z_]", "_", name.replace(":", "__"))

def export_bias_data(cond: pd.DataFrame, consensus: pd.DataFrame, responses: pd.DataFrame, bank: ItemBank,
                     feats: pd.DataFrame, out_dir: str | Path, spelling_method: str) -> tuple[Path, Path]:
    """R'da karma model için düz veri dosyaları (toplam ve ölçüt düzeyinde)."""
    out_dir = ensure_parent(Path(out_dir) / "x").parent
    crit = criteria_frame(bank)
    wide = cond.pivot_table(index=["response_id", "criterion_id"], columns="condition", values="score",
                            aggfunc="first")
    wide.columns = [r_safe(f"score__{c}") for c in wide.columns]
    base = (consensus[["response_id", "criterion_id", "rater1", "rater2", "consensus"]]
            .merge(responses[["response_id", "student_code", "item_id"]], on="response_id")
            .merge(crit[["item_id", "criterion_id", "bloom"]], on=["item_id", "criterion_id"]))
    crit_level = (base.merge(wide.reset_index(), on=["response_id", "criterion_id"], how="left")
                  .merge(feats, on="response_id", how="left")
                  .rename(columns={"consensus": "human_score"}))
    p1 = out_dir / "bias_data_criterion.csv"
    crit_level.to_csv(p1, index=False)
    score_cols = ["rater1", "rater2", "human_score"] + list(wide.columns)
    n_crit = crit.groupby("item_id").size()
    agg = crit_level.groupby(["response_id", "student_code", "item_id", "bloom"])[score_cols]
    tot = agg.sum(min_count=1)
    cnt = agg.count()
    tot = tot.where(cnt.values == n_crit.reindex(tot.index.get_level_values("item_id")).values[:, None])
    tot = tot.reset_index().merge(feats, on="response_id", how="left")
    p2 = out_dir / "bias_data_total.csv"
    tot.to_csv(p2, index=False)
    (out_dir / "bias_data_README.md").write_text(
        "# Yanlılık analizi veri dosyaları\n\n"
        "- `bias_data_total.csv`: yanıt başına bir satır (toplam puanlar).\n"
        "- `bias_data_criterion.csv`: yanıt × ölçüt başına bir satır.\n\n"
        "Sütunlar: `response_id`, `student_code`, `item_id`, `bloom` (alt/üst), `rater1`, `rater2`, "
        "`human_score` (altın set uzlaşı puanı), `score__<koşul>` (her koşulun puanı), `n_words` (kelime), "
        "`n_spelling_errors`, `spelling_error_rate`, `mtld`, `mattr`, `ttr`.\n"
        "Koşul adlarındaki `:` R uyumu için `__` olarak yazılmıştır (ör. `score__single_anchored__gpt`).\n\n"
        f"Yazım hatası yöntemi: {spelling_method}. Ayrıntı: README > Yanlılık analizi.\n", encoding="utf-8")
    return p1, p2
