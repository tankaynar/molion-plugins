#!/usr/bin/env python3
"""Writes templates/*.json, the plugin's scene templates, from orbitals/drawing.py.

    python3 tools/build_templates.py          # write them
    python3 tools/build_templates.py --check  # exit 1 if any is out of date (tests run this)

Each template is {"items": [...]}, items being the payloads of Molion's add-image,
add-annotation and add-from-molfile operations (Molion's scene templates).
Molecules are molfiles drawn with 1.5 Å bonds, which Molion reads at its bond length (50.8);
add-from-molfile centres a molecule's atoms on its x, y, so orbitals here sit on its atoms.
Standard library only, like the plugin.
"""

from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from orbitals import drawing, model  # noqa: E402

BOND = 50.8                 # Molion's bond, canvas units
ANGSTROM_BOND = 1.5         # the same bond in a molfile
LOCKS = ['replace', 'crop', 'rotate']


def orbital_item(kind: str, x: float, y: float, angle: float | None = None, phase: str = 'shaded') -> dict:
    orbital = model.new_orbital(kind, angle)
    orbital['phase'] = phase
    picture = drawing.drawing(orbital)
    return {'type': 'image', 'x': round(x, 2), 'y': round(y, 2),
            'width': picture['width'], 'height': picture['height'],
            'vector': picture, 'pluginData': model.dump(orbital), 'locks': LOCKS}


def text_item(text: str, x: float, y: float, size: float = 20) -> dict:
    return {'type': 'annotation', 'text': text, 'x': round(x, 2), 'y': round(y, 2), 'fontSize': size}


def molecule(atoms: list[tuple[str, float, float]], bonds: list[tuple[int, int, int]]) -> tuple[dict, list[tuple[float, float]]]:
    """A molecule item (atoms in canvas units, y down) and where its atoms land once placed at
    the origin: add-from-molfile centres the atoms' bounding box there."""
    xs = [x for _, x, _ in atoms]
    ys = [y for _, _, y in atoms]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    scale = ANGSTROM_BOND / BOND
    lines = ['', '  Molion Orbitals', '', f'{len(atoms):3d}{len(bonds):3d}  0  0  0  0  0  0  0  0999 V2000']
    for element, x, y in atoms:
        lines.append(f'{x * scale:10.4f}{-y * scale:10.4f}{0.0:10.4f} {element:<3s} 0  0  0  0  0  0  0  0  0  0  0  0')
    for a, b, order in bonds:
        lines.append(f'{a:3d}{b:3d}{order:3d}  0  0  0  0')
    lines.append('M  END')
    item = {'type': 'molecule', 'molfile': '\n'.join(lines) + '\n', 'x': 0, 'y': 0}
    return item, [(x - cx, y - cy) for _, x, y in atoms]


def sp3_set() -> dict:
    # A tetrahedron as textbooks draw it: up, lower left, lower right, and one behind.
    angles = [-90, 30, 150, 75]
    items = [orbital_item('sp3', 0, 0, a) for a in angles]
    items[-1]['vector'] = drawing.drawing({**model.load(items[-1]['pluginData']), 'phase': 'none'})
    items[-1]['pluginData'] = model.dump({**model.load(items[-1]['pluginData']), 'phase': 'none'})
    return {'items': items}


def sp2_set() -> dict:
    items = [orbital_item('sp2', 0, 0, a) for a in (0, 120, 240)]
    items.append(orbital_item('p', 0, 0, -90, phase='none'))
    return {'items': items}


def sp_set() -> dict:
    items = [orbital_item('sp', 0, 0, a) for a in (0, 180)]
    items.append(orbital_item('p', 0, 0, -90, phase='none'))
    items.append(orbital_item('p', 0, 0, -45, phase='none'))
    return {'items': items}


def h2_sigma() -> dict:
    gap = 34.0
    return {'items': [orbital_item('s', -gap / 2, 0), orbital_item('s', gap / 2, 0),
                      text_item('H', -gap / 2, 44), text_item('H', gap / 2, 44)]}


def ethylene_pi() -> dict:
    mol, placed = molecule([('C', 0, 0), ('C', BOND, 0)], [(1, 2, 2)])
    return {'items': [orbital_item('p', x, y) for x, y in placed] + [mol]}


def benzene_p() -> dict:
    ring = [(BOND * math.cos(math.radians(90 + 60 * i)), BOND * math.sin(math.radians(90 + 60 * i))) for i in range(6)]
    atoms = [('C', x, y) for x, y in ring]
    bonds = [(i + 1, (i + 1) % 6 + 1, 2 if i % 2 == 0 else 1) for i in range(6)]
    mol, placed = molecule(atoms, bonds)
    return {'items': [orbital_item('p', x, y) for x, y in placed] + [mol]}


TEMPLATES = {
    'sp3-set.json': sp3_set,
    'sp2-set.json': sp2_set,
    'sp-set.json': sp_set,
    'h2-sigma.json': h2_sigma,
    'ethylene-pi.json': ethylene_pi,
    'benzene-p.json': benzene_p,
}


def text_of(build) -> str:
    return json.dumps(build(), ensure_ascii=False, indent=1) + '\n'


def main(argv: list[str]) -> int:
    folder = os.path.join(ROOT, 'templates')
    os.makedirs(folder, exist_ok=True)
    stale = []
    for name, build in TEMPLATES.items():
        path = os.path.join(folder, name)
        text = text_of(build)
        current = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if current == text:
            continue
        if '--check' in argv:
            stale.append(name)
        else:
            with open(path, 'w', encoding='utf-8', newline='\n') as file:
                file.write(text)
    if stale:
        print('out of date: ' + ', '.join(stale) + ' (run tools/build_templates.py)', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
