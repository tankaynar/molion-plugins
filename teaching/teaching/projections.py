"""Fischer and Haworth projections drawn as real atoms and bonds, so the formula, the
analysis and the exports still read them as the molecule they are. The chemistry (which
group sits where) comes from Molion's get-projection; this file only lays it out.

Each layout is a list of atoms [{key, element, label, x, y}] and bonds [{a, b, order, stereo}]
naming atoms by key, in canvas units about (0, 0); actions.py draws them with add-atom and
add-bond.
"""

from __future__ import annotations

from .geometry import BOND


def _atom(key: str, group: dict | None, x: float, y: float, element: str = 'C', label: str | None = None) -> dict:
    """An atom for a group from the projection answer: its element, and its label unless it is
    just that element (H, Cl…)."""
    if group is not None:
        element = group.get('element') or element
        label = group.get('label')
    if label == element:
        label = None
    return {'key': key, 'element': element, 'label': label, 'x': round(x, 2), 'y': round(y, 2)}


def fischer(answer: dict, wedges: bool = False) -> tuple[list[dict], list[dict]]:
    """The chain upright: the top group, each centre with its left and right groups, the bottom
    group. With `wedges` the horizontal bonds are wedged toward the viewer, which is what the
    cross means, so the drawing keeps its stereo; without, it is the plain cross textbooks print."""
    rows = answer['chain']
    atoms = [_atom('top', answer['top'], 0, 0)]
    bonds = []
    previous = 'top'
    for k, row in enumerate(rows, start=1):
        key = f'c{k}'
        y = k * BOND
        atoms.append(_atom(key, None, 0, y))
        bonds.append({'a': previous, 'b': key, 'order': 'Single', 'stereo': 'None'})
        if 'double' in row:
            atoms.append(_atom(f'{key}r', row['double'], BOND, y))
            bonds.append({'a': key, 'b': f'{key}r', 'order': 'Double', 'stereo': 'None'})
        else:
            for side, dx in (('left', -BOND), ('right', BOND)):
                atoms.append(_atom(f'{key}{side[0]}', row[side], dx, y))
                bonds.append({'a': key, 'b': f'{key}{side[0]}', 'order': 'Single',
                              'stereo': 'Up' if wedges else 'None'})
        previous = key
    atoms.append(_atom('bottom', answer['bottom'], 0, (len(rows) + 1) * BOND))
    bonds.append({'a': previous, 'b': 'bottom', 'order': 'Single', 'stereo': 'None'})
    return atoms, bonds


# Ring positions in bond lengths, oxygen first, then C1, C2… clockwise seen from above: the
# oxygen at the back right, C1 at the right, the front edge toward the viewer.
PYRANOSE = [(0.5, -0.35), (1.05, 0.0), (0.5, 0.4), (-0.5, 0.4), (-1.05, 0.0), (-0.5, -0.35)]
FURANOSE = [(0.0, -0.45), (0.85, -0.05), (0.5, 0.4), (-0.5, 0.4), (-0.85, -0.05)]
STEM = 0.62          # a group's bond up or down, in bond lengths


def haworth(answer: dict) -> tuple[list[dict], list[dict]]:
    """The ring flat, its front edges bold, each group straight up or down from its carbon."""
    places = PYRANOSE if answer['ringSize'] == 6 else FURANOSE
    ring = answer['ring']
    atoms, bonds = [], []
    for k, (px, py) in enumerate(places):
        atoms.append(_atom(f'r{k}', None, px * BOND, py * BOND, element='O' if k == 0 else 'C'))
    count = len(places)
    for k in range(count):
        a, b = k, (k + 1) % count
        # The front edge, nearest the viewer: C1–C2 round to C3–C4 (C4 is the last carbon of
        # a furanose, the one before the last of a pyranose).
        front = 1 <= a and b == a + 1 and b <= 4
        bonds.append({'a': f'r{a}', 'b': f'r{b}', 'order': 'Single', 'stereo': 'UpOrDown' if front else 'None'})
    position = {atom_id: k for k, atom_id in enumerate(ring)}
    used: dict[tuple[int, bool], int] = {}
    for n, group in enumerate(answer['substituents']):
        k = position.get(group['ringAtom'])
        if k is None:
            continue
        px, py = places[k]
        up = bool(group['up'])
        # A second group the same way (two carbons off C5 in a ketose) leans out a little.
        lean = used.get((k, up), 0)
        used[(k, up)] = lean + 1
        x = (px + (0.35 * lean if px >= 0 else -0.35 * lean)) * BOND
        y = (py + (-STEM if up else STEM)) * BOND
        key = f's{n}'
        atoms.append(_atom(key, group, x, y))
        bonds.append({'a': f'r{k}', 'b': key, 'order': 'Single', 'stereo': 'None'})
    return atoms, bonds


def offset(atoms: list[dict], dx: float, dy: float) -> list[dict]:
    return [{**atom, 'x': round(atom['x'] + dx, 2), 'y': round(atom['y'] + dy, 2)} for atom in atoms]


def width(atoms: list[dict]) -> tuple[float, float]:
    xs = [a['x'] for a in atoms]
    return (min(xs), max(xs))
