"""Cycles sulla GPU quando c'è, altrimenti sulla CPU: il dispositivo usato si dichiara sempre.

Da chiamare dopo read_factory_settings, che azzera le preferenze:

  sys.path.insert(0, ".claude/skills/production-3d/scripts")
  from cycles_device import use_gpu
  use_gpu(scene)

La build di Blender in apt non ha i kernel GPU: installa quella ufficiale con
`bash .claude/tools/setup_tools.sh --blender`.
"""
import bpy

BACKENDS = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")


def use_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in BACKENDS:
        try:
            prefs.compute_device_type = backend
        except TypeError:  # backend assente in questa build
            continue
        prefs.get_devices()
        gpus = [d.name for d in prefs.get_devices_for_type(backend) if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = "GPU"
            scene.cycles.denoising_use_gpu = True
            print(f"DISPOSITIVO GPU {backend}: {', '.join(gpus)}")
            return backend
    scene.cycles.device = "CPU"
    print("DISPOSITIVO CPU: nessuna GPU disponibile per questa build di Blender")
    return "CPU"
