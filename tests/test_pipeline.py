#!/usr/bin/env python3
"""Test di regressione sulla pipeline (niente modelli, niente GUI).

Gira contro i moduli VERI (dfpro.engine / dfpro.tracking), non su repliche:
serve a dimostrare che refactor e modifiche non cambiano il comportamento
già verificato. Non richiede insightface né webcam.

    python3 tests/test_pipeline.py
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dfpro.engine import FaceEngine          # noqa: E402
from dfpro.tracking import FaceStabilizer    # noqa: E402

OK = []


def check(name, cond, detail=''):
    OK.append(bool(cond))
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ''))
    if not cond:
        raise AssertionError(name)


class FakeFace:
    """Sostituto di insightface.app.common.Face per i test."""

    def __init__(self, cx, cy, half=80, score=0.9):
        self.bbox = np.array([cx - half, cy - half, cx + half, cy + half], np.float32)
        self.det_score = score
        self.kps = np.array([[cx - 30, cy - 20], [cx + 30, cy - 20], [cx, cy],
                             [cx - 20, cy + 30], [cx + 20, cy + 30]], np.float32)
        a = np.linspace(0, 2 * np.pi, 90)
        contour = np.stack([cx + 0.8 * half * np.cos(a),
                            cy + 20 + 0.9 * half * np.sin(a)], 1)
        brows = np.stack([np.linspace(cx - 50, cx + 50, 16),
                          np.full(16, cy - 55)], 1)
        self.landmark_2d_106 = np.vstack([contour, brows]).astype(np.float32)


def params(**over):
    p = dict(swap_threshold=0.35, mask_size=1.0, feather=0.08, color_strength=0.85,
             sharpen=0.2, smooth=0.3, multi_face=True, realistic_blend=True,
             mirror=False, precise_mask=True, keep_mouth=0.4, stabilize=0.5,
             forehead=0.32, color_stab=0.6, occlusion=0.0, match=False,
             match_thresh=0.35, enhance=False, occluder=False)
    p.update(over)
    return p


# ============================================================
def test_stabilizer():
    print('\n— STABILIZER —')
    rng = np.random.default_rng(0)
    st = FaceStabilizer()
    raw, smooth = [], []
    for _ in range(60):
        cx, cy = np.array([400, 240]) + rng.normal(0, 6, 2)
        f = FakeFace(cx, cy)
        raw.append(cx)
        st.update([f], 0.7)
        smooth.append((f.bbox[0] + f.bbox[2]) / 2)
    rv, sv = np.var(raw[5:]), np.var(smooth[5:])
    check('riduce il tremolìo', sv < rv * 0.5, f'var {rv:.1f} -> {sv:.1f}')

    st2 = FaceStabilizer()
    last = None
    for i in range(40):
        f = FakeFace(100 + i * 10, 240)
        st2.update([f], 0.6)
        last = (f.bbox[0] + f.bbox[2]) / 2
    check('segue un volto in movimento', last > 430, f'vero 490, seguito {last:.0f}')

    st3 = FaceStabilizer()
    for _ in range(10):
        fa, fb = FakeFace(140, 240, 40), FakeFace(540, 240, 40)
        st3.update([fa, fb], 0.7)
    ax = (fa.bbox[0] + fa.bbox[2]) / 2
    bx = (fb.bbox[0] + fb.bbox[2]) / 2
    check('due volti restano separati', abs(ax - 140) < 15 and abs(bx - 540) < 15,
          f'A={ax:.0f} B={bx:.0f}')

    f = FakeFace(300, 200)
    FaceStabilizer().update([f], 0.5)
    check('assegna track_id (serve al color-match)', getattr(f, 'track_id', None) is not None)

    f2 = FakeFace(300, 200)
    before = f2.bbox.copy()
    FaceStabilizer().update([f2], 0.0)
    check('strength 0 non altera nulla', np.allclose(f2.bbox, before))


def test_color():
    print('\n— COLOR MATCH / ANTI-FLICKER —')
    eng = FaceEngine('inesistente.onnx')     # nessun modello caricato: ok
    rng = np.random.default_rng(0)
    base = np.full((128, 128, 3), 120, np.float32)
    fake = np.full((128, 128, 3), 140, np.uint8)
    cv2.circle(fake, (64, 64), 40, (160, 150, 170), -1)

    res = {}
    for stab in (0.0, 0.7):
        eng._color_ema.clear()
        f = FakeFace(400, 240)
        f.track_id = 1
        L = []
        for t in range(80):
            aimg = np.clip(base + 8 * np.sin(t * .9) + rng.normal(0, 6), 0,
                           255).astype(np.uint8)
            rm, rs = eng._ref_color_stats(aimg, f, stab)
            out = eng._apply_color(fake, rm, rs)
            L.append(float(cv2.cvtColor(out, cv2.COLOR_BGR2LAB)[..., 0].mean()))
        res[stab] = float(np.abs(np.diff(np.array(L[10:]))).mean())
    check('color stab riduce il flicker', res[0.7] < res[0.0] * 0.5,
          f"{res[0.0]:.2f} -> {res[0.7]:.2f} L*  (-{100*(1-res[0.7]/res[0.0]):.0f}%)")

    eng._color_ema.clear()
    f = FakeFace(400, 240)
    f.track_id = 1
    for _ in range(40):
        eng._ref_color_stats(np.full((128, 128, 3), 60, np.uint8), f, 0.7)
    for _ in range(40):
        rm, _ = eng._ref_color_stats(np.full((128, 128, 3), 200, np.uint8), f, 0.7)
    check('segue comunque un cambio di luce vero', rm[0] > 150, f'L*={rm[0]:.0f}')

    eng._color_ema.clear()
    for k in range(60):
        f = FakeFace(400, 240)
        f.track_id = k
        eng._ref_color_stats(np.full((128, 128, 3), 120, np.uint8), f, 0.7)
    check('la cache EMA non cresce', len(eng._color_ema) <= 16,
          f'{len(eng._color_ema)} voci')


def test_masks():
    print('\n— MASCHERE —')
    eng = FaceEngine('inesistente.onnx')
    w, h = 854, 480
    f = FakeFace(400, 240, 90)
    s = 0.5
    M = np.array([[s, 0, 64 - s * 400], [0, s, 64 - s * 240]], np.float32)

    m0 = eng._landmark_mask_full(f, w, h, 1.0, 0.0, M)
    m1 = eng._landmark_mask_full(f, w, h, 1.0, 0.35, M)
    top = lambda m: int(np.where(m.max(axis=1) > 0.5)[0].min())
    check('forehead alza la copertura sopra le sopracciglia', top(m1) < top(m0) - 10,
          f'{top(m0)} -> {top(m1)}')

    th = np.deg2rad(20)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]], np.float32) * s
    Mr = np.zeros((2, 3), np.float32)
    Mr[:, :2] = R
    Mr[:, 2] = [64 - (R @ [400, 240])[0], 64 - (R @ [400, 240])[1]]
    IMr = cv2.invertAffineTransform(Mr)
    up = -IMr[:, 1] / (np.linalg.norm(IMr[:, 1]) + 1e-6)
    check("l'estensione fronte segue l'inclinazione", abs(up[0]) > 0.2,
          f'up={up.round(2)}')

    mm = eng._mouth_mask_full(f, w, h)
    check('mouth mask copre la bocca e non la fronte',
          mm[int(f.kps[3][1]), 400] > 0.5 and mm[240 - 80, 400] < 0.2)

    class NoLmk:
        bbox = np.array([0, 0, 80, 80], np.float32)
    check('senza landmark torna None (fallback ellisse)',
          eng._landmark_mask_full(NoLmk(), w, h, 1.0, 0.3, M) is None)

    frame = np.zeros((h, w, 3), np.uint8)
    cv2.rectangle(frame, (340, 180), (460, 320), (120, 150, 200), -1)
    cv2.rectangle(frame, (340, 240), (460, 255), (20, 20, 20), -1)
    skin = eng._skin_prob(frame)
    check('skin: pelle alta, ciuffo scuro basso',
          skin[210, 400] > 0.8 and skin[247, 400] < 0.3,
          f'pelle={skin[210,400]:.2f} ciuffo={skin[247,400]:.2f}')


def test_blend():
    print('\n— BLEND COMPLETO —')
    eng = FaceEngine('inesistente.onnx')
    rng = np.random.default_rng(3)
    h, w = 480, 854
    frame = (rng.random((h, w, 3)) * 255).astype(np.uint8)
    bgr_fake = np.full((128, 128, 3), 150, np.uint8)
    cv2.circle(bgr_fake, (64, 64), 45, (170, 160, 180), -1)
    s = 0.5
    M = np.array([[s, 0, 64 - s * 400], [0, s, 64 - s * 240]], np.float32)
    f = FakeFace(400, 240, 90)
    f.track_id = 1

    out = eng._blend(frame, bgr_fake, M, f, params())
    check('forma e tipo corretti', out.shape == frame.shape and out.dtype == np.uint8)
    corner = int(np.abs(out[:30, :30].astype(int) - frame[:30, :30].astype(int)).max())
    center = int(np.abs(out[235:245, 395:405].astype(int)
                        - frame[235:245, 395:405].astype(int)).max())
    check('sfondo intatto, volto fuso', corner == 0 and center > 0,
          f'bordo={corner} centro={center}')

    # sweep di parametri estremi: non deve mai rompersi
    bad = []
    for cs in (0.0, 1.0):
        for ms in (0.6, 1.3):
            for km in (0.0, 1.0):
                for fe in (0.02, 0.15):
                    for pm in (True, False):
                        for occ in (0.0, 1.0):
                            o = eng._blend(frame, bgr_fake, M, f,
                                           params(color_strength=cs, mask_size=ms,
                                                  keep_mouth=km, feather=fe,
                                                  precise_mask=pm, occlusion=occ))
                            if o.shape != frame.shape or o.dtype != np.uint8:
                                bad.append((cs, ms, km, fe, pm, occ))
    check('64 combinazioni di parametri estremi reggono', not bad, f'{len(bad)} rotte')

    # riuso della skin map == ricalcolo
    p = params(occlusion=0.6)
    a = eng._blend(frame, bgr_fake, M, f, p, skin=eng._skin_prob(frame))
    eng._color_ema.clear()
    f.track_id = 1
    b = eng._blend(frame, bgr_fake, M, f, p, skin=None)
    check('skin riusata dà lo stesso risultato', np.array_equal(a, b))


def test_interpolation_choice():
    print('\n— SCELTA INTERPOLAZIONE (documentata nel codice) —')
    rng = np.random.default_rng(1)
    n = 384
    gt = np.zeros((n, n, 3), np.float32)
    yy, xx = np.mgrid[0:n, 0:n] / n
    gt[..., 0] = 120 + 60 * np.sin(3 * np.pi * yy)
    gt[..., 1] = 130 + 50 * np.cos(2.5 * np.pi * xx)
    gt[..., 2] = 150 + 40 * np.sin(2 * np.pi * (xx + yy))
    cv2.ellipse(gt, (n // 2, n // 2), (int(n * .3), int(n * .4)), 0, 0, 360,
                (205, 180, 170), -1)
    gt = np.clip(gt, 0, 255).astype(np.uint8)
    crop = cv2.resize(gt, (128, 128), interpolation=cv2.INTER_AREA)
    s = 128 / n
    IM = cv2.invertAffineTransform(np.array([[s, 0, 0], [0, s, 0]], np.float32))

    def psnr(a, b):
        e = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
        return 99.0 if e == 0 else 10 * np.log10(255.0 ** 2 / e)

    p_lin = psnr(gt, cv2.warpAffine(crop, IM, (n, n), flags=cv2.INTER_LINEAR))
    p_cub = psnr(gt, cv2.warpAffine(crop, IM, (n, n), flags=cv2.INTER_CUBIC))
    check('LINEAR resta il più fedele nel paste-back', p_lin > p_cub,
          f'LINEAR {p_lin:.2f} dB > CUBIC {p_cub:.2f} dB')

    a = cv2.warpAffine(gt, np.array([[s, 0, 0], [0, s, 0]], np.float32), (128, 128),
                       flags=cv2.INTER_AREA)
    l = cv2.warpAffine(gt, np.array([[s, 0, 0], [0, s, 0]], np.float32), (128, 128),
                       flags=cv2.INTER_LINEAR)
    check('warpAffine ignora INTER_AREA (identico a LINEAR)', np.array_equal(a, l))


if __name__ == '__main__':
    test_stabilizer()
    test_color()
    test_masks()
    test_blend()
    test_interpolation_choice()
    print(f'\n🎉 {len(OK)}/{len(OK)} controlli superati')
