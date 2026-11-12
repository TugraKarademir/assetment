"""CPU düzeni: iş yükü/süre tahmini, kısa gerekçe kipi, daraltılmış ablasyon, yapılandırmalar."""
import pandas as pd
import pytest

from scoring.benchmark import project, workload
from scoring.config import load_models
from scoring.layers import PromptRenderer
from scoring.pipeline import CONDITION_PLANS


def test_workload_counts():
    w = workload(1200, 3200, ["a", "b", "c"], "agg", "ablation")
    abl = w[w["aşama"].str.startswith("ablasyon")]
    assert abl[abl.model_key == "a"].calls.sum() == 4 * 1200 and abl[abl.model_key == "agg"].calls.sum() == 1200
    assert abl.calls.sum() == 15600
    core = workload(1200, 3200, ["a", "b", "c"], "agg", "ablation_core")
    assert core[core["aşama"].str.startswith("ablasyon")].calls.sum() == 15600 - 3600
    assert w.calls.sum() == 15600 + 3600 + 14000


def test_projection_uses_slowest_parallel_server():
    w = workload(100, 100, ["a", "b"], "agg", "ablation_core", stability=False)
    speed = pd.DataFrame({"model_key": ["a", "b", "agg"], "sec_per_call": [36.0, 72.0, 18.0]})
    layer, phase = project(w, speed)
    k1 = layer[layer.katman == "K1 çapalı"].iloc[0]
    assert k1.bottleneck == "b" and k1.wall_hours == pytest.approx(100 * 72 * 1.05 / 3600)
    total = phase[phase["aşama"] == "TOPLAM"].iloc[0]
    assert total.wall_hours == pytest.approx((3 * 100 * 72 + 100 * 18) * 1.05 / 3600)


def test_short_rationale_changes_prompt(bank):
    kw = dict(item=bank["S1"], anchors=[], response_id="R1", response_text="x")
    _, short = PromptRenderer(rationale_style="short").render("layer1_score.j2", **kw)
    _, std = PromptRenderer(rationale_style="standard").render("layer1_score.j2", **kw)
    assert "TEK cümlelik" in short and "1–3 cümlelik" in std
    with pytest.raises(ValueError):
        PromptRenderer(rationale_style="uzun")


def test_ablation_core_skips_zeroshot_revision():
    p = CONDITION_PLANS["ablation_core"]
    assert p.layer1_zeroshot and not p.layer2_zeroshot and p.layer3


def test_cpu_panel_config():
    m = load_models("config/models.yaml")
    envs = {m.spec(k).base_url_env for k in m.scorers}
    assert len(envs) == 3                      # her puanlayıcı ayrı sunucuda
    assert all(m.spec(k).open_weights for k in [*m.scorers, m.aggregator])
    assert len({m.spec(k).family for k in [*m.scorers, m.aggregator]}) == 4
    assert all(str(m.spec(k).model_revision).startswith("sha256:") for k in m.models)
    for f in ("config/models.cpu.single.yaml", "config/models.gpu.vllm.yaml", "config/models.gpu.ollama.yaml",
              "config/models.api.yaml", "config/models.mock.yaml"):
        load_models(f)
