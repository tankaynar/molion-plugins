"""Shifts from the table: each atom's deepest HOSE code that nmrshiftdb2 has measurements
for. Deeper is more alike: four spheres is usually within a ppm or two for carbon; one sphere
is a rough guess, and the card says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import hose

CARBON = '13C'
PROTON = '1H'

# Matched no deeper than this, a shift is called uncertain on the card.
ROUGH_DEPTH = 2


@dataclass(frozen=True)
class Shift:
    value: float
    spread: float
    count: int
    depth: int

    @property
    def rough(self) -> bool:
        return self.depth <= ROUGH_DEPTH


def shift_of(table, structure, index: int, nucleus: str) -> Shift | None:
    codes = hose.codes(structure, index)
    for depth in range(len(codes), 0, -1):
        entry = table.get(nucleus, hose.key(nucleus, depth, codes[depth - 1]))
        if entry is not None:
            return Shift(entry.median, entry.spread, entry.count, depth)
    return None


def carbons(structure) -> list:
    return [a for a in structure.heavy_atoms if a.element == 'C']


def protonated(structure) -> list:
    """Heavy atoms carrying hydrogens: where ¹H signals come from."""
    return [a for a in structure.heavy_atoms if a.hydrogens > 0 and a.element != '*']
