"""A recognised structure as a V2000 molfile, for Molion's `add-from-molfile`.

No chemistry happens here: atoms and bonds are written as recognised, and Molion reads the
file (kekulising aromatic bonds, checking valence) the way it reads any other.
Coordinates are scaled so the median bond is 1.5 Å, the length Molion draws as one standard
bond, and flipped so y points up as molfiles expect.
"""

from __future__ import annotations

import math
import statistics

from . import tokens
from .structure import AROMATIC, DOUBLE, HASH, SINGLE, TRIPLE, WEDGE, Structure

BOND_LENGTH = 1.5

_BOND_TYPE = {SINGLE: 1, DOUBLE: 2, TRIPLE: 3, AROMATIC: 4, WEDGE: 1, HASH: 1}
_BOND_STEREO = {WEDGE: 1, HASH: 6}


def scale_of(structure: Structure) -> float:
    """Molfile units per picture pixel."""
    lengths = [math.dist((structure.atoms[b.begin].x, structure.atoms[b.begin].y),
                         (structure.atoms[b.end].x, structure.atoms[b.end].y))
               for b in structure.bonds]
    lengths = [length for length in lengths if length > 1e-6]
    if not lengths:
        return BOND_LENGTH / 50.0           # a lone atom: any scale will do
    return BOND_LENGTH / statistics.median(lengths)


def write(structure: Structure) -> str:
    if structure.empty:
        raise ValueError('nothing to write')
    if len(structure.atoms) > 999 or len(structure.bonds) > 999:
        raise ValueError('too large for a V2000 molfile')
    for bond in structure.bonds:
        if bond.begin == bond.end or not (0 <= bond.begin < len(structure.atoms)
                                          and 0 <= bond.end < len(structure.atoms)):
            raise ValueError(f'bond {bond.begin}-{bond.end} names no pair of atoms')

    scale = scale_of(structure)
    cx = sum(a.x for a in structure.atoms) / len(structure.atoms)
    cy = sum(a.y for a in structure.atoms) / len(structure.atoms)

    labels = [tokens.parse(atom.label) for atom in structure.atoms]
    lines = ['', '  Molion  picture-to-structure', '',
             f'{len(structure.atoms):3d}{len(structure.bonds):3d}  0  0  0  0  0  0  0  0999 V2000']

    for atom, label in zip(structure.atoms, labels):
        x = (atom.x - cx) * scale
        y = -(atom.y - cy) * scale
        # An abbreviation sits on a carbon; its alias line below is what Molion shows.
        symbol = label.element or 'C'
        lines.append(f'{x:10.4f}{y:10.4f}{0:10.4f} {symbol:<3} 0  0  0  0  0  0  0  0  0  0  0  0')

    for bond in structure.bonds:
        lines.append(f'{bond.begin + 1:3d}{bond.end + 1:3d}{_BOND_TYPE[bond.kind]:3d}'
                     f'{_BOND_STEREO.get(bond.kind, 0):3d}')

    charges = [(i + 1, label.charge) for i, label in enumerate(labels) if label.charge]
    for start in range(0, len(charges), 8):
        chunk = charges[start:start + 8]
        lines.append(f'M  CHG{len(chunk):3d}' + ''.join(f'{i:4d}{c:4d}' for i, c in chunk))

    isotopes = [(i + 1, label.isotope) for i, label in enumerate(labels) if label.isotope]
    for start in range(0, len(isotopes), 8):
        chunk = isotopes[start:start + 8]
        lines.append(f'M  ISO{len(chunk):3d}' + ''.join(f'{i:4d}{m:4d}' for i, m in chunk))

    for i, label in enumerate(labels):
        if label.alias:
            lines.append(f'A  {i + 1:3d}')
            lines.append(label.alias)

    lines.append('M  END')
    return '\n'.join(lines) + '\n'
