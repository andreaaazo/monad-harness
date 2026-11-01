#!/usr/bin/env python3
"""Applica un artwork su una superficie di una foto (mockup) con prospettiva e luce della scena.

  mockup_compose.py --scene scena.jpg --art design.png --quad "x1,y1 x2,y2 x3,y3 x4,y4" --out mockup.png
       [--blend multiply|normal|screen] [--shading 0.0–1.0] [--mask maschera.png] [--feather 1.2] [--grain 0.0–1.0]
  mockup_compose.py --scene scena.jpg --show-quad "x1,y1 …" --out guida.png   # disegna il quadrilatero per verificarlo

Angoli in ordine: alto-sinistra, alto-destra, basso-destra, basso-sinistra, in pixel della scena.
--shading trasferisce la luminanza della scena sull'artwork (pieghe, ombre, riflessi);
--blend multiply simula inchiostro su carta/tessuto chiaro, normal schermi e superfici opache.
Più artwork: ripetere lo script sull'output. Usa il venv dello studio (.claude/scripts/py).
"""
import argparse
import sys

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError as exc:
    sys.exit(f"modulo mancante ({exc.name}): bash .claude/tools/setup_tools.sh, poi .claude/scripts/py")


def parse_quad(text):
    pts = [tuple(float(v) for v in p.split(",")) for p in text.split()]
    if len(pts) != 4:
        sys.exit("--quad: servono 4 punti 'x,y'")
    return np.array(pts, dtype=np.float32)


def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scene", required=True)
    p.add_argument("--art")
    p.add_argument("--quad")
    p.add_argument("--show-quad")
    p.add_argument("--out", required=True)
    p.add_argument("--blend", choices=["multiply", "normal", "screen"], default="multiply")
    p.add_argument("--shading", type=float, default=0.6)
    p.add_argument("--mask", help="maschera in scala di grigi della superficie (bianco = visibile)")
    p.add_argument("--feather", type=float, default=0.8, help="sfumatura del bordo in px")
    p.add_argument("--grain", type=float, default=0.0, help="grana della scena riportata sull'artwork")
    p.add_argument("--supersample", type=int, default=3)
    p.add_argument("--max-aspect-error", type=float, default=0.06, help="scarto massimo di proporzioni ammesso")
    p.add_argument("--allow-stretch", action="store_true")
    a = p.parse_args()

    scene_img = Image.open(a.scene).convert("RGB")
    if a.show_quad:
        q = parse_quad(a.show_quad)
        guide = scene_img.copy()
        d = ImageDraw.Draw(guide)
        d.polygon([tuple(v) for v in q], outline=(255, 0, 80), width=3)
        for i, (x, y) in enumerate(q):
            d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(255, 0, 80), width=3)
            d.text((x + 8, y + 8), "TL TR BR BL".split()[i], fill=(255, 0, 80))
        guide.save(a.out)
        print(f"scritto: {a.out}")
        return
    if not (a.art and a.quad):
        sys.exit("servono --art e --quad (o --show-quad)")

    scene = np.asarray(scene_img).astype(np.float32) / 255.0
    H, W = scene.shape[:2]
    art = load_rgba(a.art)
    ah, aw = art.shape[:2]
    quad = parse_quad(a.quad)

    # Proporzioni: stima dai lati medi del quadrilatero (approssimata in forte prospettiva).
    # Un artwork stirato è il difetto più comune dei mockup.
    top, bottom = np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3])
    left, right = np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1])
    surface_ratio = ((top + bottom) / 2) / ((left + right) / 2)
    art_ratio = aw / ah
    mismatch = abs(art_ratio / surface_ratio - 1)
    if mismatch > a.max_aspect_error and not a.allow_stretch:
        sys.exit(f"proporzioni: artwork {art_ratio:.3f} vs superficie ≈{surface_ratio:.3f} ({mismatch * 100:.1f}%). "
                 f"L'artwork verrebbe deformato: adatta la tavola alla superficie (padding) o usa --allow-stretch "
                 f"se la stima è falsata dalla prospettiva.")

    # Warp in supersampling per bordi antialiasati, poi riduzione con filtro ad area.
    s = max(1, a.supersample)
    src = np.array([[0, 0], [aw, 0], [aw, ah], [0, ah]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, quad * s)
    warped = cv2.warpPerspective(art, M, (W * s, H * s), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    warped = cv2.resize(warped, (W, H), interpolation=cv2.INTER_AREA)
    warped = np.clip(warped, 0, 1)
    rgb, alpha = warped[..., :3], warped[..., 3:4]
    if a.feather > 0:
        alpha = cv2.GaussianBlur(alpha, (0, 0), a.feather)[..., None] * (alpha > 0)
    if a.mask:
        m = np.asarray(Image.open(a.mask).convert("L").resize((W, H))).astype(np.float32)[..., None] / 255.0
        alpha = alpha * m

    # Luce della scena: luminanza locale normalizzata sulla mediana della superficie.
    lum = (scene @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))[..., None]
    inside = alpha[..., 0] > 0.5
    ref = float(np.median(lum[inside])) if inside.any() else 0.5
    light = np.clip(lum / max(ref, 1e-3), 0, 2.0)
    shaded = rgb * (1 - a.shading + a.shading * light)
    if a.grain > 0:
        hi = lum - cv2.GaussianBlur(lum, (0, 0), 2.0)[..., None]
        shaded = shaded + a.grain * hi

    if a.blend == "multiply":
        # Inchiostro su superficie chiara: la luce della scena passa già attraverso la moltiplicazione.
        comp = scene * rgb
    elif a.blend == "screen":
        comp = 1 - (1 - scene) * (1 - rgb)
    else:
        # Superficie opaca o schermo: la luce si trasferisce con --shading.
        comp = shaded
    out = scene * (1 - alpha) + np.clip(comp, 0, 1) * alpha
    Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(a.out)
    print(f"scritto: {a.out}  ({W}×{H}, blend {a.blend}, shading {a.shading})")


if __name__ == "__main__":
    main()
