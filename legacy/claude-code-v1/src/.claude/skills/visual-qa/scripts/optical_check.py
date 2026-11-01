#!/usr/bin/env python3
"""Misure percettive su un render: la precisione geometrica deve sostenere il risultato ottico.

  optical_check.py comp.png [--bg auto|#FFFFFF] [--out annot.png]          # una composizione o un segno
  optical_check.py --set icona1.png icona2.png …                           # coerenza ottica di un set

Composizione: area d'inchiostro, bounding box, baricentro della massa visiva, scarto del
baricentro dal centro geometrico della tavola, dal centro della bounding box e dal centro
ottico (per convenzione leggermente sopra il centro geometrico), distribuzione per quadranti,
equilibrio sinistra/destra e alto/basso. Il disegno annotato mostra i quattro centri.
Set: area d'inchiostro e baricentro di ogni elemento rispetto alla mediana del set; segnala
gli elementi otticamente più pesanti o più leggeri e quelli decentrati.

Sono misure, non verdetti: un baricentro decentrato può essere voluto. Servono a decidere
consapevolmente le correzioni ottiche e a documentarle.
"""
import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")


def ink(img, bg):
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba).astype(float) / 255
    alpha = arr[..., 3]
    if alpha.min() < 0.99:  # trasparenza: la massa è l'alpha
        return alpha
    rgb = arr[..., :3]
    if bg == "auto":
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        ref = np.median(border, axis=0)
    else:
        h = bg.lstrip("#")
        ref = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    # Peso visivo come distanza dal fondo (contrasto locale), saturata.
    return np.clip(np.linalg.norm(rgb - ref, axis=2) / 0.6, 0, 1)


def measure(mask):
    h, w = mask.shape
    total = mask.sum()
    if total <= 0:
        return None
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = (xs * mask).sum() / total, (ys * mask).sum() / total
    on = mask > 0.5
    yy, xx = np.nonzero(on) if on.any() else (np.array([0]), np.array([0]))
    bbox = (int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max()))
    q = [mask[:h // 2, :w // 2].sum(), mask[:h // 2, w // 2:].sum(), mask[h // 2:, :w // 2].sum(), mask[h // 2:, w // 2:].sum()]
    q = [v / total for v in q]
    return {"w": w, "h": h, "area": float(total / (w * h)), "cx": cx, "cy": cy, "bbox": bbox, "quadrants": q}


def cmd_single(a):
    img = Image.open(a.image)
    m = measure(ink(img, a.bg))
    if not m:
        sys.exit("nessuna massa visiva rilevata")
    w, h = m["w"], m["h"]
    bx0, by0, bx1, by1 = m["bbox"]
    bbc = ((bx0 + bx1) / 2, (by0 + by1) / 2)
    optical = (w / 2, h / 2 - a.optical_lift * h)
    pct = lambda dx, dy: f"{dx / w * 100:+.2f}% x, {dy / h * 100:+.2f}% y"
    q = m["quadrants"]
    print(f"{a.image}: {w}×{h} px, area d'inchiostro {m['area'] * 100:.2f}%")
    print(f"  bounding box: {bx0},{by0} → {bx1},{by1}")
    print(f"  baricentro: {m['cx']:.1f}, {m['cy']:.1f}")
    print(f"  baricentro − centro tavola:   {pct(m['cx'] - w / 2, m['cy'] - h / 2)}")
    print(f"  baricentro − centro bbox:     {pct(m['cx'] - bbc[0], m['cy'] - bbc[1])}")
    print(f"  baricentro − centro ottico:   {pct(m['cx'] - optical[0], m['cy'] - optical[1])}  (centro ottico {a.optical_lift * 100:.1f}% sopra)")
    print(f"  quadranti AS {q[0] * 100:.1f}% · AD {q[1] * 100:.1f}% · BS {q[2] * 100:.1f}% · BD {q[3] * 100:.1f}%")
    print(f"  equilibrio sinistra/destra {(q[0] + q[2]) * 100:.1f}/{(q[1] + q[3]) * 100:.1f} · alto/basso {(q[0] + q[1]) * 100:.1f}/{(q[2] + q[3]) * 100:.1f}")
    if a.record_by:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
        import evidence
        evidence.record_auto(a.image, "optical_check", "MEASURED", a.record_by, proof=a.out,
                             note=f"massa−ottico {(m['cx'] - optical[0]) / w * 100:+.2f}% x {(m['cy'] - optical[1]) / h * 100:+.2f}% y; "
                                  f"sx/dx {(q[0] + q[2]) * 100:.0f}/{(q[1] + q[3]) * 100:.0f}")
        print("  prova registrata: optical_check MEASURED (misura eseguita, non giudizio: la correzione si decide guardando)")
    if a.out:
        an = img.convert("RGB").copy()
        d = ImageDraw.Draw(an)
        def cross(x, y, col, label):
            r = max(6, w // 80)
            d.line((x - r, y, x + r, y), fill=col, width=2)
            d.line((x, y - r, x, y + r), fill=col, width=2)
            d.text((x + r + 2, y + 2), label, fill=col)
        d.rectangle(m["bbox"], outline=(0, 160, 255), width=1)
        cross(w / 2, h / 2, (120, 120, 120), "tavola")
        cross(*bbc, (0, 160, 255), "bbox")
        cross(*optical, (0, 170, 90), "ottico")
        cross(m["cx"], m["cy"], (230, 0, 80), "massa")
        an.save(a.out)
        print(f"  annotato: {a.out} (guardalo)")


def cmd_set(a):
    rows = []
    for f in a.set:
        m = measure(ink(Image.open(f), a.bg))
        if m:
            rows.append((f, m))
    if len(rows) < 2:
        sys.exit("servono almeno due elementi misurabili")
    areas = np.array([m["area"] for _, m in rows])
    med = float(np.median(areas))
    flagged = 0
    print(f"{len(rows)} elementi, area d'inchiostro mediana {med * 100:.2f}%")
    for f, m in rows:
        dev = m["area"] / med - 1
        off_x = (m["cx"] - m["w"] / 2) / m["w"] * 100
        off_y = (m["cy"] - m["h"] / 2) / m["h"] * 100
        heavy = abs(dev) > a.max_area_dev
        off = max(abs(off_x), abs(off_y)) > a.max_offset
        flagged += heavy or off
        print(f"  {'!!' if heavy or off else 'ok'} {f}: area {m['area'] * 100:.2f}% ({dev * 100:+.1f}% dalla mediana), "
              f"baricentro {off_x:+.1f}% x {off_y:+.1f}% y"
              + ("  PESO OTTICO FUORI SET" if heavy else "") + ("  DECENTRATO" if off else ""))
    print("SET " + ("COERENTE" if not flagged else f"{flagged} elementi da rivedere a occhio"))
    sys.exit(1 if flagged else 0)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", nargs="?")
    p.add_argument("--set", nargs="+")
    p.add_argument("--bg", default="auto")
    p.add_argument("--out")
    p.add_argument("--optical-lift", type=float, default=0.02, help="quota dell'altezza sopra il centro geometrico")
    p.add_argument("--max-area-dev", type=float, default=0.15)
    p.add_argument("--max-offset", type=float, default=3.0, help="%% dal centro della cella")
    p.add_argument("--record-by", help="registra la misura in evidence.py come questo agente")
    a = p.parse_args()
    if a.set:
        cmd_set(a)
    elif a.image:
        cmd_single(a)
    else:
        p.error("indica un'immagine o --set")


if __name__ == "__main__":
    main()
