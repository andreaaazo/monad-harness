#!/usr/bin/env python3
"""Controlli tecnici su un render motion: metadati, screening dei flash, raccordo del loop.

  motion_probe.py render.mp4 [--loop] [--json]

Screening flash: luminanza relativa per pixel (sRGB decodificato) a bassa risoluzione;
una transizione conta se almeno --area della superficie cambia di ≥0.10 con il
lato scuro < 0.80, come nella definizione WCAG di flash generale. Più di 3 flash
(coppie di transizioni opposte) in un secondo → FLAG. È uno screening a schermo
intero: non sostituisce un'analisi PEAT/Harding né la misura dell'area per angolo visivo.
Richiede ffmpeg/ffprobe e numpy.
"""
import argparse
import json
import shutil
import subprocess
import sys

try:
    import numpy as np
except ImportError:
    sys.exit("numpy non disponibile: motion_probe.py lo richiede")


def probe(path):
    res = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True)
    if res.returncode:
        sys.exit(f"ffprobe: {res.stderr.strip()}")
    return json.loads(res.stdout)


def frames_gray(path, width):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={width}:-2:flags=area,format=rgb24",
           "-f", "rawvideo", "-"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode:
        sys.exit(f"ffmpeg: {res.stderr.decode(errors='replace').strip()}")
    return res.stdout


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("--loop", action="store_true", help="valuta il raccordo ultimo→primo frame")
    p.add_argument("--area", type=float, default=0.25, help="frazione minima di superficie per una transizione")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        sys.exit("ffmpeg/ffprobe non disponibili")

    info = probe(args.video)
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if not video:
        sys.exit("nessuno stream video")
    audio = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    num, den = (int(v) for v in video.get("avg_frame_rate", "0/1").split("/"))
    fps = num / den if den else 0.0
    w, h = int(video["width"]), int(video["height"])
    pix = video.get("pix_fmt", "")
    report = {
        "file": args.video, "codec": video.get("codec_name"), "profile": video.get("profile"),
        "size": [w, h], "fps": round(fps, 3), "pix_fmt": pix,
        "alpha": any(k in pix for k in ("yuva", "rgba", "argb", "bgra", "gbrap", "ya")),
        "duration_s": round(float(info["format"].get("duration", 0)), 3),
        "audio": [{"codec": a.get("codec_name"), "sample_rate": a.get("sample_rate"),
                   "channels": a.get("channels")} for a in audio],
    }

    sw = 96
    sh = max(2, round(h * sw / w / 2) * 2)
    raw = frames_gray(args.video, sw)
    frame_bytes = sw * sh * 3
    n = len(raw) // frame_bytes
    rgb = np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8).reshape(n, sh, sw, 3) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lum = lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722
    report["frames_decoded"] = int(n)

    transitions = []
    for i in range(1, n):
        a, b = lum[i - 1], lum[i]
        delta = b - a
        darker = np.minimum(a, b)
        mask = (np.abs(delta) >= 0.10) & (darker < 0.80)
        if mask.mean() >= args.area:
            transitions.append((i, 1 if delta[mask].mean() > 0 else -1))
    flashes = []
    for (i1, s1), (i2, s2) in zip(transitions, transitions[1:]):
        if s1 != s2:
            flashes.append(i2)
    worst = 0
    window = max(1, round(fps)) if fps else 1
    for k, start in enumerate(flashes):
        worst = max(worst, sum(1 for f in flashes[k:] if f - start < window))
    report["flash_screen"] = {"transitions": len(transitions), "flashes": len(flashes),
                              "max_flashes_in_1s": worst, "result": "FLAG" if worst > 3 else "OK (screening)"}

    if n >= 2:
        steps = np.abs(np.diff(lum, axis=0)).mean(axis=(1, 2))
        seam = float(np.abs(lum[0] - lum[-1]).mean())
        report["motion_per_frame_median"] = round(float(np.median(steps)), 5)
        if args.loop:
            # Un raccordo pulito ha un salto ultimo→primo simile al movimento normale tra due frame.
            ratio = seam / max(float(np.median(steps)), 1e-6)
            report["loop_seam"] = {"last_to_first": round(seam, 5), "ratio_to_median_step": round(ratio, 2),
                                   "result": "OK" if ratio <= 3 else "CHECK"}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for k, v in report.items():
            print(f"{k}: {v}")
    sys.exit(1 if report["flash_screen"]["result"] == "FLAG" else 0)


if __name__ == "__main__":
    main()
