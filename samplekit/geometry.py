"""Procedural triangle meshes for the sample library.

Every primitive is centered on the origin and forms a closed surface. The
service rejects degenerate triangles (facetproof.meshes.validate_mesh), so the
helpers below keep distinct vertices and faces, and the curved primitives are
self-oriented: each triangle winding is flipped when its computed normal faces
the interior. Box winding is fixed by construction and stays correct after the
translations used when boxes are combined into one mesh.
"""
import math


def _orient(vertices, faces):
    """Flip any triangle whose winding points toward the interior.

    Only valid for geometry centered on the origin, which is the contract of
    every primitive in this module.
    """
    oriented = []
    for a, b, c in faces:
        va, vb, vc = vertices[a], vertices[b], vertices[c]
        ex = [vb[i] - va[i] for i in range(3)]
        ey = [vc[i] - va[i] for i in range(3)]
        normal = [ex[1] * ey[2] - ex[2] * ey[1],
                  ex[2] * ey[0] - ex[0] * ey[2],
                  ex[0] * ey[1] - ex[1] * ey[0]]
        center = [(va[i] + vb[i] + vc[i]) / 3 for i in range(3)]
        if sum(normal[i] * center[i] for i in range(3)) < 0:
            oriented.append([a, c, b])
        else:
            oriented.append([a, b, c])
    return oriented


def box(name, size):
    """Axis-aligned box with the given full side lengths."""
    sx, sy, sz = (v / 2 for v in size)
    vertices = [[x * sx, y * sy, z * sz]
                for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    faces = [[0, 3, 2], [0, 2, 1],          # z- bottom
             [4, 5, 6], [4, 6, 7],          # z+ top
             [0, 1, 5], [0, 5, 4],          # y- front
             [3, 7, 6], [3, 6, 2],          # y+ back
             [0, 4, 7], [0, 7, 3],          # x- left
             [1, 2, 6], [1, 6, 5]]          # x+ right
    return {"name": name, "vertices": vertices, "faces": faces}


def frustum(name, segments, radius_bottom, radius_top, height):
    """Z-axis conical frustum (cylinder when both radii agree)."""
    h = height / 2
    vertices, rings = [], []
    for z, radius in ((-h, radius_bottom), (h, radius_top)):
        ring = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            ring.append(len(vertices))
            vertices.append([radius * math.cos(angle), radius * math.sin(angle), z])
        rings.append(ring)
    bottom, top = rings
    bottom_center = len(vertices)
    vertices.append([0, 0, -h])
    top_center = len(vertices)
    vertices.append([0, 0, h])
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        bi, bj, ti, tj = bottom[i], bottom[j], top[i], top[j]
        faces.append([bi, bj, tj])
        faces.append([bi, tj, ti])
        faces.append([top_center, ti, tj])
        faces.append([bottom_center, bj, bi])
    return {"name": name, "vertices": vertices, "faces": _orient(vertices, faces)}


def cylinder(name, segments, radius, height):
    return frustum(name, segments, radius, radius, height)


def sphere(name, rings, segments, radius):
    """Latitude/longitude sphere with singular poles collapsed to one vertex."""
    vertices = [[0, 0, radius], [0, 0, -radius]]
    pole_n, pole_s = 0, 1
    ring_ids = []
    for k in range(1, rings):
        phi = math.pi * k / rings
        ring = []
        for i in range(segments):
            lam = 2 * math.pi * i / segments
            ring.append(len(vertices))
            vertices.append([radius * math.sin(phi) * math.cos(lam),
                             radius * math.sin(phi) * math.sin(lam),
                             radius * math.cos(phi)])
        ring_ids.append(ring)
    faces = []
    first = ring_ids[0]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append([pole_n, first[i], first[j]])
    for k in range(len(ring_ids) - 1):
        upper, lower = ring_ids[k], ring_ids[k + 1]
        for i in range(segments):
            j = (i + 1) % segments
            faces.append([upper[i], lower[i], lower[j]])
            faces.append([upper[i], lower[j], upper[j]])
    last = ring_ids[-1]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append([pole_s, last[j], last[i]])
    return {"name": name, "vertices": vertices, "faces": _orient(vertices, faces)}


def combined_boxes(name, members):
    """Merge several translated boxes into one mesh (shared faces may overlap)."""
    vertices, faces = [], []
    for size, translation in members:
        part = box(name + "-part", size)
        offset = len(vertices)
        for vertex in part["vertices"]:
            vertices.append([vertex[i] + translation[i] for i in range(3)])
        faces.extend([[index + offset for index in face] for face in part["faces"]])
    return {"name": name, "vertices": vertices, "faces": faces}
