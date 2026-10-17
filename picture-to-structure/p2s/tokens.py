"""Atom labels as MolScribe writes them, read into what a molfile needs.

MolScribe spells each atom as SMILES does: "C", "Cl", aromatic "c", or a bracket atom such as
"[NH+]", "[13CH3]" or "[O-]". It also writes abbreviations it recognised in brackets ("[OMe]",
"[Ph]", "[CO2Et]", "[R1]"), and R groups as numbered dummy atoms ("[2*]"). Those are kept
as text, atom aliases Molion shows and expands as labels; nothing here knows what an
abbreviation means. As upstream does, its abbreviation and R-group names are checked before
element symbols, so tosyl is not tennessine nor aryl argon.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ELEMENTS = frozenset("""
H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br
Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er
Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md
No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og D T
""".split())

# SMILES' organic subset, which needs no brackets; lower case is aromatic.
ORGANIC = {'B', 'C', 'N', 'O', 'P', 'S', 'F', 'Cl', 'Br', 'I'}
AROMATIC = {'b': 'B', 'c': 'C', 'n': 'N', 'o': 'O', 'p': 'P', 's': 'S', 'se': 'Se', 'as': 'As', 'te': 'Te'}

# The names MolScribe's own post-processing takes as abbreviations or R groups before trying
# them as atoms; only those that are also element symbols matter here (constants.py upstream).
NOT_ELEMENTS = frozenset({'Ac', 'Pr', 'Ts', 'Ar', 'Ra', 'Rb', 'Y'})

_NUMBERED_R = re.compile(r'^\[(\d+)\*\]$')

_BRACKET = re.compile(
    r'^\[(?P<isotope>\d+)?(?P<symbol>[A-Z][a-z]?|se|as|te|[bcnops])'
    r'(?P<chiral>@{1,2})?(?P<h>H\d*)?(?P<charge>[+-]+\d*|[+-]\d+)?(?::\d+)?\]$')


@dataclass(frozen=True)
class AtomLabel:
    element: str | None        # None for an abbreviation
    charge: int = 0
    isotope: int | None = None
    aromatic: bool = False
    alias: str | None = None   # the text to show in the atom's place ("OMe")


def parse(label: str) -> AtomLabel:
    """Reads one atom label. Anything that is not an element is kept as an alias."""
    text = label.strip()
    inner = text[1:-1] if text.startswith('[') and text.endswith(']') else text
    if inner in NOT_ELEMENTS:
        return AtomLabel(None, alias=inner)
    numbered = _NUMBERED_R.match(text)
    if numbered:
        return AtomLabel(None, alias=f'R{int(numbered[1])}')
    if inner == '*':
        return AtomLabel(None, alias='R')
    if text in ORGANIC:
        return AtomLabel(text)
    if text in AROMATIC:
        return AtomLabel(AROMATIC[text], aromatic=True)
    match = _BRACKET.match(text)
    if match:
        symbol = match['symbol']
        aromatic = symbol in AROMATIC
        element = AROMATIC.get(symbol, symbol)
        if element in ELEMENTS:
            return AtomLabel(element, _charge(match['charge']),
                             int(match['isotope']) if match['isotope'] else None, aromatic)
    if text in ELEMENTS:
        return AtomLabel(text)
    return AtomLabel(None, alias=inner or '?')


def _charge(text: str | None) -> int:
    if not text:
        return 0
    sign = 1 if text[0] == '+' else -1
    digits = text.lstrip('+-')
    if digits:
        return sign * int(digits)
    return sign * len(text)                 # "++" is +2
