"""Uyum metrikleri ve öğrenci düzeyinde kümelenmiş bootstrap."""
from __future__ import annotations

import numpy as np

METRICS = ["qwk", "icc2_1", "icc3_1", "exact", "adjacent", "mae", "smd"]


def qwk(a, b, lo: int | None = None, hi: int | None = None) -> float:
    """İkinci dereceden ağırlıklı kappa. Puan değerlerinin kendisi kullanılır (boşluklu etiketlerde de doğru)."""
    a, b = np.asarray(a, int), np.asarray(b, int)
    if len(a) == 0:
        return np.nan
    lo = min(a.min(), b.min()) if lo is None else lo
    hi = max(a.max(), b.max()) if hi is None else hi
    k = hi - lo + 1
    if k < 2:
        return np.nan
    ai, bi = a - lo, b - lo
    O = np.bincount(ai * k + bi, minlength=k * k).reshape(k, k).astype(float)
    E = np.outer(np.bincount(ai, minlength=k), np.bincount(bi, minlength=k)) / len(a)
    idx = np.arange(k)
    W = (idx[:, None] - idx[None, :]) ** 2 / (k - 1) ** 2
    den = (W * E).sum()
    return np.nan if den == 0 else 1 - (W * O).sum() / den


def icc(ratings: np.ndarray) -> tuple[float, float]:
    """ICC(2,1) (iki yönlü rastgele, mutlak uyum) ve ICC(3,1) (iki yönlü karma, tutarlılık); Shrout & Fleiss (1979).

    ratings: n_hedef × k_puanlayıcı
    """
    Y = np.asarray(ratings, float)
    n, k = Y.shape
    if n < 2:
        return np.nan, np.nan
    gm = Y.mean()
    ss_r = k * ((Y.mean(axis=1) - gm) ** 2).sum()
    ss_c = n * ((Y.mean(axis=0) - gm) ** 2).sum()
    ss_e = ((Y - gm) ** 2).sum() - ss_r - ss_c
    msr, msc, mse = ss_r / (n - 1), ss_c / (k - 1), ss_e / ((n - 1) * (k - 1))
    d2 = msr + (k - 1) * mse + k * (msc - mse) / n
    d3 = msr + (k - 1) * mse
    return (np.nan if d2 == 0 else (msr - mse) / d2), (np.nan if d3 == 0 else (msr - mse) / d3)


def smd(human, machine) -> float:
    """Standartlaştırılmış ortalama farkı: (ort_m − ort_h) / √((s²_m + s²_h)/2)  (Williamson ve ark., 2012)."""
    h, m = np.asarray(human, float), np.asarray(machine, float)
    sd = np.sqrt((h.var(ddof=1) + m.var(ddof=1)) / 2) if len(h) > 1 else np.nan
    return np.nan if not sd else (m.mean() - h.mean()) / sd


def all_metrics(human, machine, lo: int | None = None, hi: int | None = None) -> dict[str, float]:
    h, m = np.asarray(human, float), np.asarray(machine, float)
    if len(h) == 0:
        return {k: np.nan for k in METRICS}
    i2, i3 = icc(np.column_stack([h, m]))
    d = np.abs(h - m)
    return {"qwk": qwk(h.astype(int), m.astype(int), lo, hi), "icc2_1": i2, "icc3_1": i3,
            "exact": float((d == 0).mean()), "adjacent": float((d <= 1).mean()), "mae": float(d.mean()),
            "smd": smd(h, m)}


def weighted_metrics(human, machine, W: np.ndarray, lo: int | None = None, hi: int | None = None) -> dict[str, np.ndarray]:
    """Satır ağırlıklarıyla (W: tekrar × n, her satırın yeniden örneklemde kaç kez yer aldığı) vektörleştirilmiş
    metrikler. Tamsayı ağırlıklarda sonuç, satırları çoğaltarak hesaplanan değerle BİREBİR aynıdır."""
    h, m = np.asarray(human, float), np.asarray(machine, float)
    W = np.atleast_2d(np.asarray(W, float))
    N = W.sum(axis=1)
    d = np.abs(h - m)
    with np.errstate(invalid="ignore", divide="ignore"):
        exact = W @ (d == 0) / N
        adjacent = W @ (d <= 1) / N
        mae = W @ d / N
        mh, mm = W @ h / N, W @ m / N
        vh = (W @ h ** 2 - N * mh ** 2) / (N - 1)
        vm = (W @ m ** 2 - N * mm ** 2) / (N - 1)
        sd = np.sqrt((vh + vm) / 2)
        smd_ = np.where(sd > 0, (mm - mh) / sd, np.nan)
        # ICC(2,1), ICC(3,1) — k = 2 puanlayıcı, ağırlıklı iki yönlü ANOVA
        k = 2
        gm = (mh + mm) / 2
        rowm = (h + m) / 2
        ss_r = k * (W @ rowm ** 2 - N * gm ** 2)
        ss_c = N * ((mh - gm) ** 2 + (mm - gm) ** 2)
        ss_t = W @ (h ** 2 + m ** 2) - k * N * gm ** 2
        ss_e = ss_t - ss_r - ss_c
        msr, msc, mse = ss_r / (N - 1), ss_c / (k - 1), ss_e / ((N - 1) * (k - 1))
        d2 = msr + (k - 1) * mse + k * (msc - mse) / N
        d3 = msr + (k - 1) * mse
        icc2 = np.where(d2 != 0, (msr - mse) / d2, np.nan)
        icc3 = np.where(d3 != 0, (msr - mse) / d3, np.nan)
        # QWK
        hi_, mi_ = h.astype(int), m.astype(int)
        lo = int(min(hi_.min(), mi_.min())) if lo is None else lo
        hi = int(max(hi_.max(), mi_.max())) if hi is None else hi
        K = hi - lo + 1
        if K < 2:
            q = np.full(len(N), np.nan)
        else:
            a, b = hi_ - lo, mi_ - lo
            Oh = np.zeros((len(h), K)); Oh[np.arange(len(h)), a] = 1
            Om = np.zeros((len(h), K)); Om[np.arange(len(h)), b] = 1
            idx = np.arange(K)
            Wq = (idx[:, None] - idx[None, :]) ** 2 / (K - 1) ** 2
            obs = W @ Wq[a, b]                        # Σ w_i * ağırlık(h_i, m_i)
            Hh, Hm = W @ Oh, W @ Om                   # tekrar × K histogramlar
            exp_ = np.einsum("rk,kl,rl->r", Hh, Wq, Hm) / N
            q = np.where(exp_ != 0, 1 - obs / exp_, np.nan)
    return {"qwk": q, "icc2_1": icc2, "icc3_1": icc3, "exact": exact, "adjacent": adjacent, "mae": mae, "smd": smd_}


class ClusterBootstrap:
    """Öğrenci düzeyinde kümelenmiş bootstrap: her tekrarda öğrenciler yerine koyarak çekilir ve seçilen
    öğrencinin (ilgili kapsamdaki) tüm yanıtları alınır. Uygulamada her tekrar, satırların seçilme sayısını
    veren bir ağırlık vektörüdür (vektörleştirilmiş, satır çoğaltmayla birebir eşdeğer).
    Aynı tohum + aynı küme listesi => koşullar arasında aynı yeniden örneklemler (eşleştirilmiş karşılaştırma)."""

    def __init__(self, clusters: np.ndarray, reps: int, seed: int):
        self.clusters = np.asarray(clusters)
        uniq, inv = np.unique(self.clusters, return_inverse=True)
        G = len(uniq)
        rng = np.random.default_rng(seed)
        draws = rng.integers(0, G, size=(reps, G))
        counts = np.zeros((reps, G))
        np.add.at(counts, (np.repeat(np.arange(reps), G), draws.ravel()), 1)
        self.W = counts[:, inv]
        self.draws = draws
        self.groups = [np.flatnonzero(inv == g) for g in range(G)]

    def indices(self):
        """Satır dizinleri olarak yeniden örneklemler (test/denetim amaçlı)."""
        for d in self.draws:
            yield np.concatenate([self.groups[g] for g in d])

    def metrics(self, human, machine, lo=None, hi=None, ci: float = 0.95) -> dict[str, tuple[float, float, float]]:
        point = all_metrics(human, machine, lo, hi)
        boot = weighted_metrics(human, machine, self.W, lo, hi)
        a = (1 - ci) / 2
        return {k: (point[k], float(np.nanquantile(boot[k], a)), float(np.nanquantile(boot[k], 1 - a)))
                for k in METRICS}

    def paired_diff(self, human, m1, m2, metric: str = "qwk", lo=None, hi=None, ci: float = 0.95):
        point = all_metrics(human, m1, lo, hi)[metric] - all_metrics(human, m2, lo, hi)[metric]
        diffs = weighted_metrics(human, m1, self.W, lo, hi)[metric] - weighted_metrics(human, m2, self.W, lo, hi)[metric]
        q = (1 - ci) / 2
        p_two = 2 * min(np.nanmean(diffs <= 0), np.nanmean(diffs >= 0))
        return point, float(np.nanquantile(diffs, q)), float(np.nanquantile(diffs, 1 - q)), min(1.0, p_two)
