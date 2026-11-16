"""Declarative, versioned catalog of the synthetic sample collection.

Everything here is pure data so a re-run of the commissioning tool produces the
same request against the same frozen definition. Mesh and pigment resource
keys are stable identifiers: the commissioning tool maps each key to the
service id assigned inside a data root and never guesses an id across runs.

Coverage matrix across the ten samples:
  * lenses: perspective and orthographic, four camera positions and both FOVs
  * materials: matte / satin / glossy, single- and two-sided pigments
  * sampling: 1x and 2x supersampling, square and rectangular canvases
  * geometry: five primitive families composed into five-to-six part assemblies
"""
from . import geometry

SPEC_VERSION = "samplekit-catalog-1"

# ---------------------------------------------------------------------------
# Mesh resources, keyed by stable names. The same key always means the same
# vertex/face definition within SPEC_VERSION.
# ---------------------------------------------------------------------------
MESHES = {
    "bracket": geometry.combined_boxes("角形支架", [
        ([3.2, 2.4, 0.4], [0, 0, -0.55]),       # horizontal foot
        ([0.4, 2.4, 1.7], [-1.4, 0, 0.5]),      # upright rib
        ([1.5, 0.5, 0.9], [-0.45, 0.95, 0.1]),  # gusset
    ]),
    "post": geometry.cylinder("立柱", 20, 0.28, 2.0),
    "shaft": geometry.cylinder("横销", 14, 0.18, 1.8),
    "knob": geometry.frustum("锥形把手", 18, 0.42, 0.26, 0.55),
    "hexbase": geometry.frustum("六角座", 6, 0.62, 0.62, 0.5),
    "sphere": geometry.sphere("球头", 6, 16, 0.34),
    "plate": geometry.box("垫板", [1.2, 1.0, 0.25]),
}

# Pigment resources. Roughness/specular span the material range and the
# two_sided flag exercises both culling paths in the planner.
PIGMENTS = {
    "matte_blue": {"name": "哑蓝", "color": [0.10, 0.32, 0.62],
                   "roughness": 0.90, "specular": 0.05, "two_sided": True},
    "satin_red": {"name": "缎红", "color": [0.72, 0.16, 0.14],
                  "roughness": 0.55, "specular": 0.25, "two_sided": True},
    "gloss_amber": {"name": "亮琥珀", "color": [0.92, 0.58, 0.12],
                    "roughness": 0.12, "specular": 0.85, "two_sided": False},
    "matte_green": {"name": "哑绿", "color": [0.18, 0.55, 0.30],
                    "roughness": 0.80, "specular": 0.10, "two_sided": True},
    "satin_gray": {"name": "缎灰", "color": [0.58, 0.60, 0.63],
                   "roughness": 0.45, "specular": 0.35, "two_sided": False},
    "deep_violet": {"name": "深紫", "color": [0.38, 0.18, 0.58],
                    "roughness": 0.65, "specular": 0.20, "two_sided": True},
}

# A placement references catalog mesh/pigment keys and an optional transform.
def P(key, mesh, pigment, transform=None, visible=True):
    return {"key": key, "mesh": mesh, "pigment": pigment,
            "transform": transform or {}, "visible": visible}


def L(projection="perspective", eye=(4.5, -5.0, 3.6), target=(0, 0, 0.15),
      fov=45, span=5.0):
    lens = {"projection": projection, "eye": list(eye), "target": list(target),
            "up": [0, 0, 1]}
    if projection == "perspective":
        lens["fov"] = fov
    else:
        lens["span"] = span
    return lens


SAMPLES = [
    {
        "id": "S01",
        "title": "角架立柱总成 · 透视主视角 · 1x 采样",
        "placements": [
            P("bracket", "bracket", "matte_blue", {"translation": [0, 0, 0]}),
            P("post", "post", "satin_gray", {"translation": [0.7, -0.4, 0.55]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.7, -0.4, 1.15], "euler": [0, 90, 0]}),
            P("knob", "knob", "satin_red",
              {"translation": [0.7, -0.4, 1.75], "euler": [180, 0, 0]}),
            P("footpad", "plate", "matte_green", {"translation": [0.7, -0.4, -0.32]}),
        ],
        "lens": L("perspective", (4.5, -5.0, 3.6), fov=45),
        "request": {"width": 160, "height": 160, "samples": 1},
    },
    {
        "id": "S02",
        "title": "角架立柱总成 · 正交投影 · 1x 采样",
        "placements": [
            P("bracket", "bracket", "matte_blue"),
            P("post", "post", "satin_gray", {"translation": [0.7, -0.4, 0.55]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.7, -0.4, 1.15], "euler": [0, 90, 0]}),
            P("knob", "knob", "satin_red",
              {"translation": [0.7, -0.4, 1.75], "euler": [180, 0, 0]}),
            P("footpad", "plate", "matte_green", {"translation": [0.7, -0.4, -0.32]}),
        ],
        "lens": L("orthographic", (4.5, -5.0, 3.6), span=5.2),
        "request": {"width": 160, "height": 160, "samples": 1},
    },
    {
        "id": "S03",
        "title": "角架立柱总成 · 透视主视角 · 2x 超采样",
        "placements": [
            P("bracket", "bracket", "matte_blue"),
            P("post", "post", "satin_gray", {"translation": [0.7, -0.4, 0.55]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.7, -0.4, 1.15], "euler": [0, 90, 0]}),
            P("knob", "knob", "satin_red",
              {"translation": [0.7, -0.4, 1.75], "euler": [180, 0, 0]}),
            P("footpad", "plate", "matte_green", {"translation": [0.7, -0.4, -0.32]}),
        ],
        "lens": L("perspective", (4.5, -5.0, 3.6), fov=45),
        "request": {"width": 160, "height": 160, "samples": 2},
    },
    {
        "id": "S04",
        "title": "角架立柱总成 · 侧向俯视 · 窄视场 · 2x 超采样",
        "placements": [
            P("bracket", "bracket", "matte_blue", {"euler": [0, 0, 12]}),
            P("post", "post", "satin_gray",
              {"translation": [0.7, -0.4, 0.55], "euler": [0, 0, 12]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.7, -0.4, 1.15], "euler": [0, 90, 12]}),
            P("knob", "knob", "satin_red",
              {"translation": [0.7, -0.4, 1.75], "euler": [180, 0, 12]}),
            P("footpad", "plate", "matte_green",
              {"translation": [0.7, -0.4, -0.32], "euler": [0, 0, 12]}),
        ],
        "lens": L("perspective", (-5.2, -1.4, 2.6), target=(0, 0, 0.3), fov=32),
        "request": {"width": 192, "height": 128, "samples": 2},
    },
    {
        "id": "S05",
        "title": "六角座球头机构 · 低机位透视 · 1x 采样",
        "placements": [
            P("hexbase", "hexbase", "satin_gray", {"translation": [0, 0, -0.5]}),
            P("post", "post", "deep_violet",
              {"translation": [0, 0, 0.75], "scale": [0.85, 0.85, 0.85]}),
            P("arm", "shaft", "gloss_amber",
              {"translation": [0.55, 0, 1.45], "euler": [0, 90, 0]}),
            P("ball", "sphere", "satin_red", {"translation": [1.35, 0, 1.45]}),
            P("cap", "knob", "matte_green",
              {"translation": [0, 0, 1.75], "euler": [180, 0, 0]}),
            P("shim", "plate", "matte_blue", {"translation": [0, 0, -0.12]}),
        ],
        "lens": L("perspective", (2.2, -4.6, 1.4), target=(0.2, 0, 0.5), fov=52),
        "request": {"width": 144, "height": 192, "samples": 1},
    },
    {
        "id": "S06",
        "title": "六角座球头机构 · 正交正视 · 2x 超采样",
        "placements": [
            P("hexbase", "hexbase", "satin_gray", {"translation": [0, 0, -0.5]}),
            P("post", "post", "deep_violet",
              {"translation": [0, 0, 0.75], "scale": [0.85, 0.85, 0.85]}),
            P("arm", "shaft", "gloss_amber",
              {"translation": [0.55, 0, 1.45], "euler": [0, 90, 0]}),
            P("ball", "sphere", "satin_red", {"translation": [1.35, 0, 1.45]}),
            P("cap", "knob", "matte_green",
              {"translation": [0, 0, 1.75], "euler": [180, 0, 0]}),
            P("shim", "plate", "matte_blue", {"translation": [0, 0, -0.12]}),
        ],
        "lens": L("orthographic", (0, -6.0, 1.2), target=(0.2, 0, 0.5), span=4.6),
        "request": {"width": 144, "height": 192, "samples": 2},
    },
    {
        "id": "S07",
        "title": "双销支架 · 高机位透视 · 宽视场 · 1x 采样",
        "placements": [
            P("bracket", "bracket", "satin_red", {"euler": [0, 18, 0]}),
            P("post_a", "post", "matte_blue",
              {"translation": [0.7, -0.4, 0.55], "euler": [0, 18, 0]}),
            P("post_b", "post", "deep_violet",
              {"translation": [-0.7, 0.5, 0.55], "euler": [0, 18, 0],
               "scale": [0.7, 0.7, 0.7]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.0, 0.05, 1.2], "euler": [0, 90, 18]}),
            P("ball", "sphere", "satin_gray", {"translation": [1.05, -0.4, 1.72]}),
        ],
        "lens": L("perspective", (3.4, 3.8, 5.4), fov=60),
        "request": {"width": 200, "height": 150, "samples": 1},
    },
    {
        "id": "S08",
        "title": "双销支架 · 高机位透视 · 2x 超采样",
        "placements": [
            P("bracket", "bracket", "satin_red", {"euler": [0, 18, 0]}),
            P("post_a", "post", "matte_blue",
              {"translation": [0.7, -0.4, 0.55], "euler": [0, 18, 0]}),
            P("post_b", "post", "deep_violet",
              {"translation": [-0.7, 0.5, 0.55], "euler": [0, 18, 0],
               "scale": [0.7, 0.7, 0.7]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.0, 0.05, 1.2], "euler": [0, 90, 18]}),
            P("ball", "sphere", "satin_gray", {"translation": [1.05, -0.4, 1.72]}),
        ],
        "lens": L("perspective", (3.4, 3.8, 5.4), fov=60),
        "request": {"width": 200, "height": 150, "samples": 2},
    },
    {
        "id": "S09",
        "title": "旋转角架 · 对侧机位透视 · 1x 采样",
        "placements": [
            P("bracket", "bracket", "matte_green", {"euler": [0, -25, 0]}),
            P("post", "post", "satin_gray",
              {"translation": [0.7, -0.4, 0.55], "euler": [0, -25, 0]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.7, -0.4, 1.15], "euler": [0, 65, 0]}),
            P("knob", "knob", "deep_violet",
              {"translation": [0.7, -0.4, 1.75], "euler": [180, -25, 0]}),
            P("hexbase", "hexbase", "satin_red",
              {"translation": [-0.6, 0.6, -0.45], "euler": [0, -25, 30]}),
            P("footpad", "plate", "matte_blue",
              {"translation": [0.7, -0.4, -0.32], "euler": [0, -25, 0]}),
        ],
        "lens": L("perspective", (-4.0, 4.6, 3.0), fov=40),
        "request": {"width": 176, "height": 176, "samples": 1},
    },
    {
        "id": "S10",
        "title": "旋转角架 · 对侧机位透视 · 2x 超采样",
        "placements": [
            P("bracket", "bracket", "matte_green", {"euler": [0, -25, 0]}),
            P("post", "post", "satin_gray",
              {"translation": [0.7, -0.4, 0.55], "euler": [0, -25, 0]}),
            P("shaft", "shaft", "gloss_amber",
              {"translation": [0.7, -0.4, 1.15], "euler": [0, 65, 0]}),
            P("knob", "knob", "deep_violet",
              {"translation": [0.7, -0.4, 1.75], "euler": [180, -25, 0]}),
            P("hexbase", "hexbase", "satin_red",
              {"translation": [-0.6, 0.6, -0.45], "euler": [0, -25, 30]}),
            P("footpad", "plate", "matte_blue",
              {"translation": [0.7, -0.4, -0.32], "euler": [0, -25, 0]}),
        ],
        "lens": L("perspective", (-4.0, 4.6, 3.0), fov=40),
        "request": {"width": 176, "height": 176, "samples": 2},
    },
]

# Illumination applied to every sample; directional key fill plus ambient.
ILLUMINATION = {
    "ambient": 0.18,
    "background": [0.94, 0.95, 0.97],
    "lights": [
        {"direction": [3, -4, 6], "intensity": 0.85, "color": [1, 0.97, 0.92]},
        {"direction": [-4, 2, 3], "intensity": 0.35, "color": [0.85, 0.9, 1]},
    ],
}
