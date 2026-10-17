"""A molecule as Molion sends it (the `structures` of a `card` request, which is also what
`get-structure` returns): atoms with their perceived aromaticity, hydrogens and symmetry
class, and bonds by position in the atom list.

Drawn hydrogen atoms are folded into their heavy atom here: they are counted in its
`hydrogens` already, and a peak that lights a carbon lights its drawn hydrogens too.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Atom:
    index: int                  # position in the structure's atom list
    id: str | None              # the drawn atom, or None for one a label expanded into
    origin: str | None          # for an expanded atom, the labelled atom it belongs to
    element: str
    charge: int
    isotope: int | None
    hydrogens: int
    aromatic: bool
    in_ring: bool
    ring_sizes: list[int]
    hybridization: str | None
    symmetry_class: int
    # (neighbour index, bond order, aromatic bond, stereo) for heavy neighbours only.
    neighbours: list[tuple[int, float, bool, object]] = field(default_factory=list)
    # Ids of drawn H atoms bonded to it.
    drawn_hydrogens: list[str] = field(default_factory=list)

    @property
    def is_hydrogen(self) -> bool:
        return self.element == 'H'

    @property
    def drawn_ids(self) -> list[str]:
        """What lights up on the canvas for this atom: itself (or its label) and its drawn Hs."""
        own = self.id or self.origin
        return ([own] if own else []) + self.drawn_hydrogens


@dataclass
class Structure:
    molecule_id: str
    focus: set[str] | None
    atoms: list[Atom]
    error: str | None = None

    @property
    def heavy_atoms(self) -> list[Atom]:
        return [a for a in self.atoms if not a.is_hydrogen]

    def bond_between(self, a: int, b: int):
        for neighbour, order, aromatic, stereo in self.atoms[a].neighbours:
            if neighbour == b:
                return order, aromatic, stereo
        return None

    def in_focus(self, atom: Atom) -> bool:
        """Whether the selection names this atom (or there is no selection)."""
        if self.focus is None:
            return True
        return any(i in self.focus for i in atom.drawn_ids)


def read(entry: dict) -> Structure:
    """One `structures` item → Structure. Absent fields are null (the host omits nulls)."""
    raw_atoms = entry.get('atoms') or []
    atoms = [Atom(
        index=i,
        id=a.get('id'),
        origin=a.get('origin'),
        element=a.get('element') or '*',
        charge=int(a.get('charge') or 0),
        isotope=a.get('isotope'),
        hydrogens=int(a.get('hydrogens') or 0),
        aromatic=bool(a.get('aromatic')),
        in_ring=bool(a.get('inRing')),
        ring_sizes=list(a.get('ringSizes') or []),
        hybridization=a.get('hybridization'),
        symmetry_class=int(a.get('symmetryClass') or 0),
    ) for i, a in enumerate(raw_atoms)]

    for bond in entry.get('bonds') or []:
        ends = bond.get('atoms') or []
        if len(ends) != 2 or not all(0 <= e < len(atoms) for e in ends):
            continue
        a, b = atoms[ends[0]], atoms[ends[1]]
        order = bond.get('order') or 1
        aromatic = bool(bond.get('aromatic'))
        stereo = bond.get('stereo')
        if a.is_hydrogen and not b.is_hydrogen:
            if a.id:
                b.drawn_hydrogens.append(a.id)
            continue
        if b.is_hydrogen and not a.is_hydrogen:
            if b.id:
                a.drawn_hydrogens.append(b.id)
            continue
        if a.is_hydrogen and b.is_hydrogen:
            continue
        a.neighbours.append((b.index, order, aromatic, stereo))
        b.neighbours.append((a.index, order, aromatic, stereo))

    focus = entry.get('focus')
    return Structure(
        molecule_id=entry.get('moleculeId') or '',
        focus=set(focus) if focus is not None else None,
        atoms=atoms,
        error=entry.get('error'),
    )
