"""First-order ¹H multiplets: which hydrogens split a signal, and by how much.

Typical coupling constants, not predicted ones: a signal's neighbours are known from the
structure, their J from the textbook values below. Good enough to tell a triplet from a
quartet and to draw them; not a simulation of second-order spectra.

    ³J (H–C–C–H) between sp³ carbons, or an sp³ and an sp² one     7.0 Hz
    aromatic ortho (six-membered ring)                             7.8 Hz
    aromatic, five-membered ring                                   3.5 Hz
    aromatic meta (six-membered ring)                              1.8 Hz
    alkene trans                                                  16.5 Hz
    alkene cis (and any double bond in a ring of up to 7)         10.5 Hz
    alkene of unknown geometry                                    13.0 Hz
    aldehyde H to the neighbouring CH                              2.5 Hz

Hydrogens on O, N and S exchange and are shown as broad singlets, coupling to nothing.
Equivalent hydrogens (one symmetry class) do not split each other. Couplings within 1 Hz
of each other are merged, so CH₂ between CH₃ and CH₂ is a sextet, as it is seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FREQUENCY = 400.0          # MHz: how far apart lines are drawn, and what Copy says
CARBON_FREQUENCY = 101.0   # the ¹³C frequency of a 400 MHz spectrometer

EXCHANGEABLE = {'O', 'N', 'S'}
MERGE_WITHIN = 1.0
MAX_LINES = 64

J_VICINAL = 7.0
J_ORTHO = 7.8
J_FIVE_RING = 3.5
J_META = 1.8
J_TRANS = 16.5
J_CIS = 10.5
J_UNKNOWN_ALKENE = 13.0
J_ALDEHYDE = 2.5

_NAMES = {1: 'd', 2: 't', 3: 'q', 4: 'p', 5: 'sext', 6: 'sept'}


@dataclass
class Multiplet:
    name: str                                  # s, d, t, dd, m, br s …
    couplings: list[tuple[int, float]] = field(default_factory=list)   # (hydrogens, J Hz), largest J first
    lines: list[tuple[float, float]] = field(default_factory=list)     # (offset ppm, relative intensity)

    @property
    def j_text(self) -> str | None:
        """'7.8, 1.8' for the couplings a name spells out; None for s, m and br s."""
        if self.name in ('s', 'm', 'br s') or not self.couplings:
            return None
        return ', '.join(f'{j:.1f}' for _, j in self.couplings)


def multiplet_of(structure, atom) -> Multiplet:
    if atom.element in EXCHANGEABLE:
        return Multiplet('br s')

    inequivalent_self = _own_hydrogens_differ(structure, atom)
    partners: list[tuple[int, float]] = []
    for neighbour_index, order, aromatic, stereo in atom.neighbours:
        neighbour = structure.atoms[neighbour_index]
        if neighbour.hydrogens == 0 or neighbour.element in EXCHANGEABLE or neighbour.element == '*':
            continue
        if neighbour.symmetry_class == atom.symmetry_class:
            continue
        partners.extend(_vicinal(structure, atom, neighbour, order, aromatic, stereo))

    # Meta coupling round a benzene-like ring: through one ring atom to the next.
    if atom.aromatic and 6 in atom.ring_sizes:
        ortho = {n for n, _, aromatic, _ in atom.neighbours if aromatic}
        for middle in ortho:
            for far, _, aromatic, _ in structure.atoms[middle].neighbours:
                other = structure.atoms[far]
                if (far == atom.index or far in ortho or not aromatic or other.hydrogens == 0
                        or other.symmetry_class == atom.symmetry_class
                        or not _share_ring(structure, atom.index, far, 6)):
                    continue
                partners.append((other.hydrogens, J_META))

    groups = _merge(partners)
    if inequivalent_self:
        return Multiplet('m', groups)
    return Multiplet(_name(groups), groups, _lines(groups))


def _vicinal(structure, atom, neighbour, order, aromatic, stereo) -> list[tuple[int, float]]:
    if aromatic and atom.aromatic and neighbour.aromatic:
        sizes = set(atom.ring_sizes) & set(neighbour.ring_sizes)
        return [(neighbour.hydrogens, J_ORTHO if 6 in sizes else J_FIVE_RING if 5 in sizes else J_VICINAL)]
    if neighbour.aromatic != atom.aromatic and (atom.aromatic or neighbour.aromatic):
        return []          # a hydrogen on a ring and one beside it: too far, or not there at all
    if order == 2:
        if neighbour.hydrogens == 2:
            # A terminal =CH₂: one hydrogen trans, one cis.
            return [(1, J_TRANS), (1, J_CIS)]
        return [(neighbour.hydrogens, _alkene_j(structure, atom, neighbour, stereo))]
    if order == 1:
        if _is_aldehyde(structure, atom) or _is_aldehyde(structure, neighbour):
            return [(neighbour.hydrogens, J_ALDEHYDE)]
        return [(neighbour.hydrogens, J_VICINAL)]
    return []


def _alkene_j(structure, atom, neighbour, stereo) -> float:
    if atom.in_ring and neighbour.in_ring and any(
            size <= 7 for size in set(atom.ring_sizes) & set(neighbour.ring_sizes)):
        return J_CIS
    if isinstance(stereo, dict) and stereo.get('relation') in ('cis', 'trans'):
        # The relation is of the two reference atoms, one on each end. With one hydrogen
        # and one other substituent on each carbon, the hydrogens lie the same way.
        if _substituents(structure, atom, neighbour) == 1 and _substituents(structure, neighbour, atom) == 1:
            return J_CIS if stereo['relation'] == 'cis' else J_TRANS
    return J_UNKNOWN_ALKENE


def _substituents(structure, atom, partner) -> int:
    return sum(1 for n, *_ in atom.neighbours if n != partner.index)


def _is_aldehyde(structure, atom) -> bool:
    return (atom.element == 'C' and atom.hydrogens == 1 and any(
        order == 2 and structure.atoms[n].element == 'O' for n, order, *_ in atom.neighbours))


def _own_hydrogens_differ(structure, atom) -> bool:
    """A =CH₂ whose other end carries two different groups: its hydrogens are not alike."""
    if atom.hydrogens != 2:
        return False
    for n, order, aromatic, _ in atom.neighbours:
        if order == 2 and not aromatic:
            other = structure.atoms[n]
            groups = [structure.atoms[m] for m, *_ in other.neighbours if m != atom.index]
            classes = [g.symmetry_class for g in groups]
            if other.hydrogens == 2:
                return False
            if other.hydrogens == 1 or len(set(classes)) > 1:
                return True
    return False


def _share_ring(structure, a: int, b: int, size: int) -> bool:
    return size in structure.atoms[a].ring_sizes and size in structure.atoms[b].ring_sizes


def _merge(partners: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Coupling groups, largest J first; groups closer than MERGE_WITHIN become one."""
    groups: list[list[float]] = []      # [count, J]
    for count, j in sorted(partners, key=lambda p: -p[1]):
        if groups and abs(groups[-1][1] - j) <= MERGE_WITHIN:
            total = groups[-1][0] + count
            groups[-1][1] = (groups[-1][1] * groups[-1][0] + j * count) / total
            groups[-1][0] = total
        else:
            groups.append([count, j])
    return [(int(c), round(j, 1)) for c, j in groups]


def _name(groups: list[tuple[int, float]]) -> str:
    if not groups:
        return 's'
    if len(groups) == 1:
        return _NAMES.get(groups[0][0], 'm')
    if len(groups) > 3 or any(count > 3 for count, _ in groups):
        return 'm'
    return ''.join(_NAMES[count] for count, _ in groups)


def _lines(groups: list[tuple[int, float]]) -> list[tuple[float, float]]:
    """The multiplet's lines around its centre, in ppm, intensities summing to 1."""
    lines = {0.0: 1.0}
    for count, j in groups:
        weights = _binomial(count)
        step = j / FREQUENCY
        split = {}
        for at, intensity in lines.items():
            for k, weight in enumerate(weights):
                where = round(at + (k - count / 2) * step, 6)
                split[where] = split.get(where, 0.0) + intensity * weight
        lines = split
        if len(lines) > MAX_LINES:
            return []
    total = sum(lines.values())
    return sorted((at, intensity / total) for at, intensity in lines.items())


def _binomial(n: int) -> list[float]:
    row = [1.0]
    for _ in range(n):
        row = [a + b for a, b in zip([0.0] + row, row + [0.0])]
    return row
