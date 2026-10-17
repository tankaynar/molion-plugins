"""An orbital as a vector picture: Molion's display-list ops, in canvas units.

Each orbital is a polar plot of its angular part, r = L·f(θ)², around its nucleus; the lobes
are where f keeps one sign, so each lobe is a closed polygon from the nucleus out and back.
The picture's box is centred on the nucleus, so the picture's centre is the atom it sits on.
"""

from __future__ import annotations

import math

from . import model

# A lobe's reach: about a bond's length (Molion draws bonds 50.8 long), as textbooks draw them.
LOBE = 56.0
SAMPLES = 120
PAD = 3.0
INK = '#000000'
SHADE_ALPHA = 'A6'
SIGN_SIZE = 16

# The back lobe reaches (1 − a)/(1 + a) of the front one's length: about 29%, 38% and 48%.
HYBRID = {'sp': 0.55, 'sp2': 0.45, 'sp3': 0.35}


def angular(kind: str):
    """f(θ) for each orbital, with its axis (or its first lobe) pointing along θ = 0."""
    return {
        's': lambda t: 1.0,
        'p': lambda t: math.cos(t),
        # Hybrids as textbooks draw them: a big lobe and a small back lobe, the back lobe
        # larger the more p character (sp < sp² < sp³). f = a + cos θ, a from HYBRID.
        'sp': lambda t: HYBRID['sp'] + math.cos(t),
        'sp2': lambda t: HYBRID['sp2'] + math.cos(t),
        'sp3': lambda t: HYBRID['sp3'] + math.cos(t),
        # The four-leaf d orbitals: dx²−y² has its lobes on the axes, the others between them.
        'dx2y2': lambda t: math.cos(2 * t),
        'dxy': lambda t: math.sin(2 * t),
        'dxz': lambda t: math.sin(2 * t),
        'dyz': lambda t: math.sin(2 * t),
        # dz²: two lobes along the axis, the ring (torus) seen edge-on across it.
        'dz2': lambda t: (3 * math.cos(t) ** 2 - 1) / 2,
    }[kind]


# r = L·|f|^power: squared gives the p and d orbitals' teardrop lobes; hybrids are plotted
# unsquared, which keeps their back lobe the size textbooks draw it (about a third).
POWER = {'sp': 1, 'sp2': 1, 'sp3': 1}
# An s orbital is drawn smaller than a lobe: a sphere round the nucleus, not a reach.
SIZE = {'s': 0.5}


def _power(kind: str) -> int:
    return POWER.get(kind, 2)


# How far each kind's largest lobe reaches before scaling, so every kind's biggest lobe is
# LOBE long (times its SIZE).
def _peak(kind: str) -> float:
    f = angular(kind)
    return max(abs(f(2 * math.pi * i / SAMPLES)) ** _power(kind) for i in range(SAMPLES)) or 1.0


def lobes(kind: str, angle: float = 0.0, scale: float = 1.0) -> list[tuple[int, list[tuple[float, float]]]]:
    """Each lobe as (sign, points around it), in canvas units about the nucleus, turned by
    `angle` degrees clockwise."""
    f = angular(kind)
    peak = _peak(kind)
    power = _power(kind)
    reach = LOBE * scale * SIZE.get(kind, 1.0)
    turn = math.radians(angle)
    values = [f(2 * math.pi * i / SAMPLES) for i in range(SAMPLES)]

    def point(i: int) -> tuple[float, float]:
        theta = 2 * math.pi * i / SAMPLES
        r = reach * abs(values[i]) ** power / peak
        return (r * math.cos(theta + turn), r * math.sin(theta + turn))

    if all(v > 0 for v in values):                  # an s orbital: one lobe all round
        return [(1, [point(i) for i in range(SAMPLES)])]

    # Runs of one sign, starting just after a sign change so no run wraps round the start.
    start = next(i for i in range(SAMPLES) if (values[i - 1] > 0) != (values[i] > 0))
    runs, current, sign = [], [], None
    for k in range(SAMPLES):
        i = (start + k) % SAMPLES
        s = 1 if values[i] > 0 else -1
        if sign is not None and s != sign:
            runs.append((sign, current))
            current = []
        sign = s
        current.append(i)
    runs.append((sign, current))
    result = []
    for sign, indices in runs:
        if len(indices) < 3:
            continue
        result.append((sign, [(0.0, 0.0)] + [point(i) for i in indices]))
    return result


def _centroid(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def ops(orbital: dict, origin: tuple[float, float] = (0.0, 0.0), scale: float = 1.0,
        preview: bool = False) -> list[dict]:
    """The orbital's ops around `origin`. A preview is drawn at angle 0: the host turns it
    to follow the drag."""
    angle = 0.0 if preview else orbital['angle']
    ox, oy = origin
    positive, negative = orbital['colours']
    result = []
    for sign, points in lobes(orbital['type'], angle, scale):
        if orbital['flip']:
            sign = -sign
        polygon = [[round(ox + x, 2), round(oy + y, 2)] for x, y in points]
        hue = positive if sign > 0 else negative
        if orbital['phase'] == 'shaded':
            result.append({'op': 'polygon', 'points': polygon, 'fill': hue + SHADE_ALPHA, 'stroke': hue, 'width': 1.5})
        else:
            result.append({'op': 'polygon', 'points': polygon, 'stroke': INK, 'width': 1.5})
        if orbital['phase'] == 'signs' and not preview:
            cx, cy = _centroid(points[1:] if len(points) > 1 else points)
            if orbital['type'] == 's':
                # Not on the nucleus: up and to the left of it, inside the sphere.
                cx, cy = cx - LOBE * scale * 0.2, cy - LOBE * scale * 0.2
            # A small lobe (a hybrid's back lobe) gets a smaller sign, so the sign stays inside it.
            extent = max(math.hypot(x, y) for x, y in points)
            size = round(max(6.0, min(SIGN_SIZE * scale, extent * 0.55)), 1)
            result.append({'op': 'text', 'text': '+' if sign > 0 else '−', 'at': [round(ox + cx, 2), round(oy + cy, 2)],
                           'align': 'middle', 'baseline': 'middle', 'size': size, 'color': INK})
    # The nucleus.
    result.append({'op': 'ellipse', 'center': [ox, oy], 'rx': 2.0 * scale, 'ry': 2.0 * scale, 'fill': INK})
    return result


def half_extent(orbital: dict) -> tuple[float, float]:
    """How far the drawing reaches from the nucleus each way, padded."""
    points = [p for _, lobe in lobes(orbital['type'], orbital['angle']) for p in lobe]
    return (max(abs(x) for x, _ in points) + PAD, max(abs(y) for _, y in points) + PAD)


def drawing(orbital: dict) -> dict:
    """The picture: {width, height, ops}, its box centred on the nucleus."""
    hx, hy = half_extent(orbital)
    hx, hy = round(max(hx, 4.0), 2), round(max(hy, 4.0), 2)
    return {'width': 2 * hx, 'height': 2 * hy, 'ops': ops(orbital, (hx, hy))}


def preview(orbital: dict) -> dict:
    """What a placement drag shows: the orbital at the press point, turned toward the pointer."""
    return {'ops': [{'op': 'group', 'origin': 'start', 'rotate': 'vector', 'ops': ops(orbital, preview=True)}]}
