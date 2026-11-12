"""Sahte (mock) sağlayıcı — API anahtarı olmadan boru hattını uçtan uca sınamak için.

Gerçek bir dil modeli DEĞİLDİR. Puanları şu şekilde üretir:
  * Katman 1 (çapalı): yanıtın her çapaya sözcük-kümesi (Jaccard) benzerliği ile ağırlıklı çapa puanı ortalaması.
  * Katman 1 (çapasız): referans yanıtla örtüşme oranından ölçeklenmiş puan.
  * Modele özgü sabit yanlılık (`bias`) + yanıta özgü deterministik gürültü (`noise`) eklenir.
  * Katman 2: kendi puanı panel ortancasından uzaksa belirli olasılıkla ona yaklaşır.
  * Katman 3: revize puanların ortancası.
Çıktı, gerçek modeller gibi JSON METNİ olarak döner; `invalid_json_rate` oranında bilerek bozuk çıktı
üretir ki doğrulama/yeniden deneme yolu da sınansın. Bağlam `LLMRequest.metadata["mock"]` ile gelir.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import time

from ..utils import normalize_for_hash
from .base import LLMRequest, LLMResult, Provider

STOP = set("ve ile bir bu da de için olarak ise çok daha en gibi olan veya ki ne mi ya o şu her".split())


def _tokens(text: str) -> set[str]:
    return {w for w in normalize_for_hash(text).split() if len(w) > 2 and w not in STOP}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


class MockProvider(Provider):
    name = "mock"
    supports_batch = False

    def _rng(self, *parts) -> random.Random:
        h = hashlib.sha256("|".join([self.spec.model, *map(str, parts)]).encode()).hexdigest()
        return random.Random(int(h[:16], 16))

    async def complete(self, req: LLMRequest) -> LLMResult:
        t0 = time.perf_counter()
        await asyncio.sleep(0)
        ctx = req.metadata["mock"]
        attempt = req.metadata.get("attempt", 0)
        rep = req.metadata.get("replicate", 1)
        rep = rep if isinstance(rep, int) else 2   # ölçüm (benchmark) etiketleri gibi sayısal olmayan replikasyonlar
        p = self.spec.params
        rng = self._rng(ctx["response_id"], ctx["task"], ctx.get("variant", ""), attempt, rep)
        n_in = int(len(req.prompt_text()) / 3.5)

        if attempt == 0 and rng.random() < p.get("invalid_json_rate", 0.0):
            text = "Puanlarım şöyle: C1=3, C2=2 (JSON üretilemedi)"
        else:
            scores = {"layer1": self._layer1, "layer2": self._layer2, "layer3": self._layer3}[ctx["task"]](ctx, rng, rep)
            crit = [{"criterion_id": cid, "score": s,
                     "rationale": f"Yanıt {cid} ölçütünde {s} düzeyindeki tanımlayıcıya en yakın.",
                     "rubric_evidence": " ".join(ctx["response_text"].split()[:8])}
                    for cid, s in scores.items()]
            out = {"item_id": ctx["item_id"], "response_id": ctx["response_id"], "criteria": crit,
                   "total": sum(scores.values()), "confidence": round(0.55 + 0.4 * rng.random(), 2)}
            if ctx["task"] == "layer2":
                out["changed"] = scores != ctx["own"]
                out["revision_reason"] = "Diğer gerekçeler rubrikle karşılaştırıldı."
            text = json.dumps(out, ensure_ascii=False)
        return LLMResult(text, n_in, int(len(text) / 3.5), self.spec.model, time.perf_counter() - t0,
                         {"mock": True})

    # -- görevler -----------------------------------------------------------------
    def _perturb(self, value: float, lo: int, hi: int, rng: random.Random, key: str, rep: int) -> int:
        p = self.spec.params
        stable = self._rng(key)  # yanıt × ölçüt için sabit gürültü (replikasyonlar arası ortak)
        v = value + p.get("bias", 0.0) + stable.gauss(0, p.get("noise", 0.5))
        if rep > 1 and rng.random() < 0.08:     # replikasyonlar arası küçük kararsızlık
            v += rng.choice([-1, 1])
        return int(min(hi, max(lo, math.floor(v + 0.5))))

    def _layer1(self, ctx, rng, rep):
        resp = _tokens(ctx["response_text"])
        out = {}
        for cid, (lo, hi) in ctx["criteria"].items():
            if ctx.get("anchors"):
                sims = [(_jaccard(resp, _tokens(a["text"])), a["scores"][cid]) for a in ctx["anchors"]]
                w = [math.exp(s / 0.04) for s, _ in sims]
                est = sum(wi * sc for wi, (_, sc) in zip(w, sims)) / sum(w)
            else:
                ref = _tokens(ctx.get("reference") or "")
                cover = len(resp & ref) / max(1, len(ref))
                est = lo + (hi - lo) * min(1.0, 2.2 * cover)
            out[cid] = self._perturb(est, lo, hi, rng, f"{ctx['response_id']}|{cid}|{ctx.get('variant')}", rep)
        return out

    def _layer2(self, ctx, rng, rep):
        out = {}
        for cid, (lo, hi) in ctx["criteria"].items():
            own = ctx["own"][cid]
            others = [o[cid] for o in ctx["others"]]
            allv = sorted([own, *others])
            med = allv[len(allv) // 2]
            out[cid] = med if (own != med and rng.random() < 0.6) else own
        return out

    def _layer3(self, ctx, rng, rep):
        out = {}
        for cid, (lo, hi) in ctx["criteria"].items():
            vals = sorted(r[cid] for r in ctx["revised"])
            med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
            out[cid] = self._perturb(med, lo, hi, rng, f"{ctx['response_id']}|{cid}|agg", rep)
        return out
