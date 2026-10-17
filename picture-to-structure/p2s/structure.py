"""What recognition finds in a picture: atoms where they were drawn, and the bonds between them.

Coordinates are the picture's own pixels (x to the right, y down), so the drawing keeps the
layout it had on the page. Nothing here knows about the model that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Bond kinds, as molfile.py writes them. For a wedge or a hash, `begin` is the narrow end.
SINGLE, DOUBLE, TRIPLE, AROMATIC, WEDGE, HASH = 'single', 'double', 'triple', 'aromatic', 'wedge', 'hash'
BOND_KINDS = (SINGLE, DOUBLE, TRIPLE, AROMATIC, WEDGE, HASH)


@dataclass(frozen=True)
class Atom:
    label: str               # as recognised: "C", "Cl", "[NH+]", "[OMe]", "c"
    x: float
    y: float
    confidence: float = 1.0


@dataclass(frozen=True)
class Bond:
    begin: int               # positions in Structure.atoms
    end: int
    kind: str = SINGLE


@dataclass
class Structure:
    atoms: list[Atom] = field(default_factory=list)
    bonds: list[Bond] = field(default_factory=list)
    confidence: float = 1.0  # the model's own score for the whole structure, 0–1

    @property
    def empty(self) -> bool:
        return not self.atoms
