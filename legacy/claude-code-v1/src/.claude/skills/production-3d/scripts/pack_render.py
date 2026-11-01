"""Render 3D di una scatola di packaging con le grafiche sulle facce (Blender, Cycles).

  blender -b -P .claude/skills/production-3d/scripts/pack_render.py -- \
      --size 120x60x180 --front fronte.png [--back retro.png] [--side lato.png] [--top alto.png] \
      --base "#EDEBE4" --out work/mockup/pack.png --blend work/source/pack.blend [--res 1600x1200] [--samples 96] [--angle 32] [--finish matte|satin|gloss]

Dimensioni in mm (larghezza × profondità × altezza): la scala è reale, quindi luce, ombre e
prospettiva rispondono alla scatola vera. Ogni grafica è mappata sulla sua faccia senza
deformazioni: le proporzioni dell'immagine devono corrispondere alla faccia (lo script lo verifica).
Luce da studio a tre punti con area light, piano d'appoggio con ombra di contatto, camera a 85 mm
equivalenti. Il render è una prova: guardalo con Read e confrontalo con la dieline.
"""
import argparse
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cycles_device import use_gpu

argv =sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
p = argparse.ArgumentParser()
p.add_argument("--size", required=True)
p.add_argument("--front", required=True)
p.add_argument("--back")
p.add_argument("--side")
p.add_argument("--top")
p.add_argument("--base", default="#EDEBE4")
p.add_argument("--out", required=True)
p.add_argument("--blend", help="salva la scena come master .blend")
p.add_argument("--res", default="1600x1200")
p.add_argument("--samples", type=int, default=96)
p.add_argument("--angle", type=float, default=32)
p.add_argument("--finish", choices=["matte", "satin", "gloss"], default="satin")
p.add_argument("--backdrop", default="#D9D6CF", help="colore del fondale")
p.add_argument("--light", type=float, default=1.0, help="moltiplicatore della luce")
p.add_argument("--exposure", type=float, default=0.0)
p.add_argument("--lens", type=float, default=85)
p.add_argument("--look", choices=["faithful", "photographic"], default="faithful")
p.add_argument("--elevation", type=float, default=14, help="gradi sopra l'orizzonte")
a = p.parse_args(argv)

W, D, H = (float(v) / 1000 for v in a.size.lower().split("x"))  # metri
rx, ry = (int(v) for v in a.res.lower().split("x"))


def hex_rgba(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
use_gpu(scene)
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = rx, ry
scene.render.film_transparent = False
# "Standard": i colori sRGB della grafica restano quelli del file (fedeltà per il packaging);
# "AgX" dà un aspetto più fotografico ma schiarisce e desatura: si sceglie con --look.
scene.view_settings.view_transform = "Standard" if a.look == "faithful" else "AgX"
scene.unit_settings.system = "METRIC"

roughness = {"matte": 0.75, "satin": 0.4, "gloss": 0.12}[a.finish]


def material(name, image=None, face_ratio=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = roughness
    if image:
        img = bpy.data.images.load(image)
        iw, ih = img.size
        if face_ratio and abs((iw / ih) / face_ratio - 1) > 0.03:
            sys.exit(f"{image}: proporzioni {iw}×{ih} ({iw / ih:.3f}) diverse dalla faccia ({face_ratio:.3f}): "
                     f"prepara la grafica alle proporzioni della faccia")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Cubic"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = hex_rgba(a.base)
    return m


# Scatola: sei facce come piani separati, ognuno con UV 0–1 sulla propria grafica.
faces = {
    "front": ((0, -D / 2, H / 2), (math.radians(90), 0, 0), (W, H), a.front),
    "back": ((0, D / 2, H / 2), (math.radians(90), 0, math.radians(180)), (W, H), a.back),
    "right": ((W / 2, 0, H / 2), (math.radians(90), 0, math.radians(90)), (D, H), a.side),
    "left": ((-W / 2, 0, H / 2), (math.radians(90), 0, math.radians(-90)), (D, H), a.side),
    "top": ((0, 0, H), (0, 0, 0), (W, D), a.top),
    "bottom": ((0, 0, 0.0001), (math.radians(180), 0, 0), (W, D), None),
}
for name, (loc, rot, (fw, fh), img) in faces.items():
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = f"face_{name}"
    ob.scale = (fw, fh, 1)
    ob.data.materials.append(material(f"m_{name}", img, fw / fh if img else None))

# Fondale curvo (cyclorama): pavimento e parete raccordati, nessun orizzonte visibile.
size = max(W, D, H)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
floor = bpy.context.active_object
floor.scale = (size * 40, size * 40, 1)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.subdivide(number_cuts=40)
bpy.ops.object.mode_set(mode="OBJECT")
R = size * 3.0  # raggio del raccordo
for v in floor.data.vertices:
    y = v.co.y * floor.scale[1]
    if y > size * 2.0:
        t = min((y - size * 2.0) / R, math.pi / 2)
        v.co.z = (R * (1 - math.cos(t)) + max(0, y - size * 2.0 - R * math.pi / 2)) / floor.scale[2]
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
bg_col = hex_rgba(a.backdrop)
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = bg_col
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
floor.data.materials.append(fm)
bpy.ops.object.shade_smooth()


def area(name, loc, watts, s):
    """Area light puntata al centro della scatola; potenza in W a una distanza di riferimento di 0.5 m,
    scalata con il quadrato della distanza reale (stessa illuminazione a qualsiasi scala)."""
    from mathutils import Vector
    bpy.ops.object.light_add(type="AREA", location=loc)
    L = bpy.context.active_object
    L.name = name
    d = (Vector(loc) - Vector((0, 0, H / 2))).length
    L.data.energy = watts * (d / 0.5) ** 2
    L.data.size = s
    L.rotation_mode = "QUATERNION"
    L.rotation_quaternion = (Vector((0, 0, H / 2)) - Vector(loc)).to_track_quat("-Z", "Y")
    return L


k = a.light * (0.55 if a.look == "faithful" else 1.0)
area("key", (-size * 2.4, -size * 2.8, size * 2.6), 6 * k, size * 2.6)
area("fill", (size * 3.0, -size * 1.8, size * 1.2), 2.2 * k, size * 3.0)
area("rim", (size * 1.0, size * 2.8, size * 2.4), 3 * k, size * 1.4)
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = bg_col
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.15

# Camera: distanza ricavata dal campo visivo perché la scatola occupi ~60% dell'altezza del quadro.
from mathutils import Vector
bpy.ops.object.camera_add()
cam = bpy.context.active_object
cam.data.lens = a.lens
cam.data.sensor_fit = "VERTICAL"
cam.data.sensor_height = 24
vfov = 2 * math.atan(12 / a.lens)
extent = max(H, math.hypot(W, D) * 0.75) * 1.1
dist = extent / (2 * math.tan(vfov / 2)) / 0.6
ang, elev = math.radians(a.angle), math.radians(a.elevation)
target = Vector((0, 0, H * 0.5))
cam.location = target + Vector((-math.sin(ang) * math.cos(elev), -math.cos(ang) * math.cos(elev), math.sin(elev))) * dist
cam.rotation_mode = "QUATERNION"
cam.rotation_quaternion = (target - cam.location).to_track_quat("-Z", "Y")
scene.camera = cam
scene.view_settings.exposure = a.exposure

scene.render.filepath = a.out
if a.blend:
    os.makedirs(os.path.dirname(os.path.abspath(a.blend)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
bpy.ops.render.render(write_still=True)
print(f"RENDER {a.out} {rx}x{ry} scatola {a.size} mm finitura {a.finish}")

# Autoverifica: fedeltà del colore del fronte e alte luci bruciate, misurate sul render.
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
out_img = bpy.data.images.load(a.out)
px = np.empty(len(out_img.pixels), dtype=np.float32)
out_img.pixels.foreach_get(px)
img = px.reshape(ry, rx, 4)[::-1, :, :3]  # Blender: origine in basso
clip = float((img.max(axis=2) >= 0.999).mean())
front = bpy.data.objects["face_front"]
corners = [front.matrix_world @ v.co for v in front.data.vertices]
uv = [world_to_camera_view(scene, cam, c) for c in corners]
xs = [u.x * rx for u in uv]
ys = [(1 - u.y) * ry for u in uv]
cx, cy = sum(xs) / 4, sum(ys) / 4
x0, x1 = int(cx - (max(xs) - min(xs)) * 0.18), int(cx + (max(xs) - min(xs)) * 0.18)
y0, y1 = int(cy - (max(ys) - min(ys)) * 0.08), int(cy + (max(ys) - min(ys)) * 0.08)
rendered = img[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)
art = bpy.data.images.load(a.front)
apx = np.empty(len(art.pixels), dtype=np.float32)
art.pixels.foreach_get(apx)
ah, aw = art.size[1], art.size[0]
apx = apx.reshape(ah, aw, 4)[::-1, :, :3]
# Stessa zona relativa della grafica (centro del fronte).
art_patch = apx[int(ah * 0.42):int(ah * 0.58), int(aw * 0.32):int(aw * 0.68)].reshape(-1, 3).mean(axis=0)


def oklab(c):
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    l = (0.4122214708 * lin[0] + 0.5363325363 * lin[1] + 0.0514459929 * lin[2]) ** (1 / 3)
    m = (0.2119034982 * lin[0] + 0.6806995451 * lin[1] + 0.1073969566 * lin[2]) ** (1 / 3)
    s_ = (0.0883024619 * lin[0] + 0.2817188376 * lin[1] + 0.6299787005 * lin[2]) ** (1 / 3)
    return np.array([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s_,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s_,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s_])


# La grafica caricata da Blender è in lineare se lo spazio è sRGB? Le immagini sRGB restano sRGB nei pixel.
de = float(np.linalg.norm(oklab(rendered) - oklab(art_patch)))
to_hex = lambda c: "#%02X%02X%02X" % tuple(int(max(0, min(1, v)) * 255 + 0.5) for v in c)
print(f"VERIFICA fronte: grafica {to_hex(art_patch)} → reso {to_hex(rendered)}  ΔEok {de:.3f}"
      + ("  (fedele)" if de < 0.06 else "  (scostamento visibile: rivedi luce/esposizione o usa --look)"))
print(f"VERIFICA alte luci bruciate: {clip * 100:.2f}% dei pixel" + ("  (troppe: abbassa --light o --exposure)" if clip > 0.01 else ""))
