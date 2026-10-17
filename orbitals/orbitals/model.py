"""An orbital as this plugin keeps it in a picture's pluginData.

{"v": 1, "type": "p", "phase": "shaded", "colours": ["#3D6FD8", "#D8553D"], "angle": -90,
 "flip": false}

`type` is the orbital (TYPES); `phase` how its sign is shown: lobes shaded in two colours,
"+" and "−" written in outlined lobes, or outlines alone; `colours` the positive and negative
lobes' colours; `angle` its axis in degrees, clockwise from pointing right (the canvas's y
grows downward); `flip` swaps the signs. The angle lives here, not in the picture's own
rotation, so the signs stay upright however the orbital is turned.
"""

from __future__ import annotations

import json
import re

VERSION = 1

TYPES = ['s', 'p', 'sp', 'sp2', 'sp3', 'dxy', 'dxz', 'dyz', 'dx2y2', 'dz2']
NAMES = {
    's': 's', 'p': 'p', 'sp': 'sp', 'sp2': 'sp²', 'sp3': 'sp³',
    'dxy': 'dxy', 'dxz': 'dxz', 'dyz': 'dyz', 'dx2y2': 'dx²−y²', 'dz2': 'dz²',
}
PHASES = ['shaded', 'signs', 'none']
PHASE_NAMES = {'shaded': 'Shaded', 'signs': '+ and −', 'none': 'Outline'}

POSITIVE = '#3D6FD8'
NEGATIVE = '#D8553D'
_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')


class OrbitalError(ValueError):
    """Something the user asked for that an orbital cannot be; the message says why."""


def new_orbital(kind: str = 'p', angle: float | None = None) -> dict:
    if kind not in TYPES:
        raise OrbitalError(f'No orbital called {kind}.')
    return {'v': VERSION, 'type': kind, 'phase': 'shaded', 'colours': [POSITIVE, NEGATIVE],
            'angle': normal_angle(default_angle(kind) if angle is None else angle), 'flip': False}


def default_angle(kind: str) -> float:
    """A p orbital stands upright, as a π system is drawn; everything else points right."""
    return -90.0 if kind == 'p' else 0.0


def normal_angle(angle: float) -> float:
    """−180 < angle ≤ 180, to a tenth of a degree."""
    angle = round(float(angle), 1) % 360.0
    return angle - 360.0 if angle > 180.0 else angle


def copy_of(orbital: dict) -> dict:
    return json.loads(json.dumps(orbital))


def dump(orbital: dict) -> str:
    return json.dumps(orbital, separators=(',', ':'), ensure_ascii=False)


def load(text: str | None) -> dict | None:
    """The orbital in a picture's pluginData, or None when it is not one of ours."""
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get('v') != VERSION or data.get('type') not in TYPES:
        return None
    orbital = new_orbital(data['type'])
    if data.get('phase') in PHASES:
        orbital['phase'] = data['phase']
    colours = data.get('colours')
    if isinstance(colours, list) and len(colours) == 2 and all(isinstance(c, str) and _HEX.match(c) for c in colours):
        orbital['colours'] = [c.upper() for c in colours]
    if isinstance(data.get('angle'), (int, float)) and not isinstance(data.get('angle'), bool):
        orbital['angle'] = normal_angle(data['angle'])
    orbital['flip'] = bool(data.get('flip'))
    return orbital


def colour(value) -> str:
    if not isinstance(value, str) or not _HEX.match(value):
        raise OrbitalError('A colour is #RRGGBB.')
    return value.upper()
