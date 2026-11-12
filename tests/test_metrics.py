"""QWK'nin sklearn ile tutarlılığı, ICC'nin Shrout & Fleiss (1979) örneğiyle doğrulanması, bootstrap eşdeğerliği."""
import numpy as np
import pytest
from sklearn.metrics import cohen_kappa_score

from scoring.metrics import ClusterBootstrap, all_metrics, icc, qwk, smd, weighted_metrics


@pytest.mark.parametrize("seed", range(10))
def test_qwk_matches_sklearn(seed):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 5, 200)
    b = np.clip(a + rng.integers(-2, 3, 200), 0, 4)
    ref = cohen_kappa_score(a, b, weights="quadratic", labels=list(range(5)))
    assert qwk(a, b, 0, 4) == pytest.approx(ref, abs=1e-12)


def test_qwk_gapped_labels_uses_score_distance():
    # Gözlenen etiketler {0, 2, 4}: sklearn'e tam etiket aralığı verildiğinde aynı sonuç
    a = np.array([0, 2, 4, 4, 2, 0, 4])
    b = np.array([0, 4, 4, 2, 2, 0, 4])
    assert qwk(a, b, 0, 4) == pytest.approx(cohen_kappa_score(a, b, weights="quadratic", labels=[0, 1, 2, 3, 4]))
    assert qwk(a, a, 0, 4) == pytest.approx(1.0)


def test_icc_shrout_fleiss_1979():
    # Shrout & Fleiss (1979) Tablo 2: 6 hedef × 4 puanlayıcı; ICC(2,1)=.29, ICC(3,1)=.71
    Y = np.array([[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]])
    i2, i3 = icc(Y)
    assert round(i2, 2) == 0.29 and round(i3, 2) == 0.71


def test_smd_and_simple_metrics():
    h = np.array([1, 2, 3, 4, 2, 3])
    m = h + 1
    r = all_metrics(h, m, 0, 5)
    assert r["exact"] == 0 and r["adjacent"] == 1 and r["mae"] == 1
    assert smd(h, m) == pytest.approx(1 / np.std(h, ddof=1))


def test_weighted_bootstrap_equals_row_duplication():
    rng = np.random.default_rng(2)
    h = rng.integers(0, 13, 80)
    m = np.clip(h + rng.integers(-2, 3, 80), 0, 12)
    bs = ClusterBootstrap(rng.integers(0, 30, 80), reps=20, seed=5)
    for W, idx in zip(bs.W, bs.indices()):
        a = all_metrics(h[idx], m[idx], 0, 12)
        b = {k: v[0] for k, v in weighted_metrics(h, m, W[None], 0, 12).items()}
        for k in a:
            assert a[k] == pytest.approx(b[k], abs=1e-9, nan_ok=True)


def test_cluster_bootstrap_keeps_students_together():
    clusters = np.array(["s1", "s1", "s2", "s3", "s3", "s3"])
    bs = ClusterBootstrap(clusters, reps=50, seed=0)
    for W in bs.W:
        assert W[0] == W[1] and W[3] == W[4] == W[5]
    # Aynı tohum => aynı yeniden örneklemler (eşleştirilmiş karşılaştırmalar için)
    assert np.array_equal(ClusterBootstrap(clusters, 50, 0).W, bs.W)
