#!/usr/bin/env python3
"""Confronto visivo tra due versioni: SSIM, quota di pixel cambiati, area del cambiamento,
mappa delle differenze. Serve a dimostrare che una correzione ha toccato solo ciò che doveva.

  pixel_diff.py prima.png dopo.png [--out diff.png] [--threshold 8] [--expect-region x,y,w,h]

--expect-region: il cambiamento deve stare dentro questo rettangolo, altrimenti FAIL (regressione).
"""
import argparse
import sys

try:
    import numpy as np
    from PIL import Image
    from skimage.metrics import structural_similarity
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--out")
    p.add_argument("--threshold", type=float, default=8, help="differenza minima per canale (0–255)")
    p.add_argument("--expect-region")
    a = p.parse_args()

    A = np.asarray(Image.open(a.before).convert("RGB")).astype(np.int16)
    B = np.asarray(Image.open(a.after).convert("RGB")).astype(np.int16)
    if A.shape != B.shape:
        sys.exit(f"dimensioni diverse: {A.shape[1]}×{A.shape[0]} vs {B.shape[1]}×{B.shape[0]}")
    diff = np.abs(A - B).max(axis=2)
    changed = diff > a.threshold
    ssim = structural_similarity(A.astype(np.uint8), B.astype(np.uint8), channel_axis=2)
    frac = float(changed.mean())
    print(f"SSIM {ssim:.5f} · pixel cambiati {frac * 100:.3f}%")
    ok = True
    if changed.any():
        ys, xs = np.nonzero(changed)
        box = (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
        print(f"area del cambiamento: x={box[0]} y={box[1]} w={box[2]} h={box[3]}")
        if a.expect_region:
            x, y, w, h = (int(v) for v in a.expect_region.split(","))
            outside = changed.copy()
            outside[y:y + h, x:x + w] = False
            if outside.any():
                ok = False
                print(f"FAIL: {int(outside.sum())} pixel cambiati fuori dalla regione attesa")
    if a.out:
        heat = np.zeros((*diff.shape, 3), dtype=np.uint8)
        base = (A.mean(axis=2) * 0.35).astype(np.uint8)
        heat[..., 0] = np.where(changed, 255, base)
        heat[..., 1] = np.where(changed, 0, base)
        heat[..., 2] = np.where(changed, 80, base)
        Image.fromarray(heat).save(a.out)
        print(f"mappa: {a.out}")
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
