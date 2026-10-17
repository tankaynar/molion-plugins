"""HOSE codes: an atom's surroundings, sphere by sphere, as a canonical string.

Written for this plugin from the idea in W. Bremser, "HOSE — a novel substructure code",
Anal. Chim. Acta 103 (1978) 355–365: describe the atoms one, two, three… bonds away, in a
fixed order, so that the same surroundings always give the same code and similar ones share
their inner spheres. A shift is then predicted from measured shifts of atoms with the same
code, from the deepest sphere that has any.

This is our own encoding, not Bremser's or CDK's character for character; the shift table is
built with this same code (tools/build_table.py), so the two always agree. Each code is the
walk tree from the centre, children sorted, so it does not depend on how atoms are numbered:

    token(atom) = element (lowercase when aromatic), its charge, '*' for an unknown group
    bond        = '' single, '=' double, '#' triple, ':' aromatic, '$' quadruple
    a branch    = bond + token + '(' + sorted branches + ')'
    a ring back to an atom already on the path is bond + '&'

Hydrogens are not atoms here; the centre's own count is part of its token.
"""

from __future__ import annotations

import hashlib

MAX_DEPTH = 5

_BONDS = {1: '', 2: '=', 3: '#', 4: '$'}


def bond_token(order: float, aromatic: bool) -> str:
    if aromatic or order == 1.5:
        return ':'
    return _BONDS.get(int(order), '')


def atom_token(atom) -> str:
    if atom.element == '*':
        return '*'
    token = atom.element.lower() if atom.aromatic else atom.element
    if atom.charge:
        sign = '+' if atom.charge > 0 else '-'
        token += sign * min(abs(atom.charge), 3)
    return token


def root_token(atom) -> str:
    return f'{atom_token(atom)}H{atom.hydrogens}'


def codes(structure, centre: int, max_depth: int = MAX_DEPTH) -> list[str]:
    """The centre's codes for 1..max_depth spheres: codes[d - 1] describes d spheres."""
    atom = structure.atoms[centre]
    levels = _walk(structure, centre, None, (centre,), max_depth)
    root = root_token(atom)
    return [f'{root}{levels[d]}' for d in range(1, max_depth + 1)]


def _walk(structure, node: int, parent: int | None, path: tuple, remaining: int) -> list[str]:
    """The subtree below `node`, as its canonical text cut at 0..remaining further levels.

    One walk gives every depth: level k of a branch is its token plus its children's level
    k - 1. Going back along the bond just walked is not a branch; reaching an atom already
    on the path closes a ring ('&').
    """
    levels = [''] * (remaining + 1)
    if remaining == 0:
        return levels
    branches = []          # per child: list of strings by level
    for neighbour, order, aromatic, _ in structure.atoms[node].neighbours:
        if neighbour == parent:
            continue
        bond = bond_token(order, aromatic)
        if neighbour in path:
            closure = bond + '&'
            branches.append([closure] * remaining)
            continue
        below = _walk(structure, neighbour, node, path + (neighbour,), remaining - 1)
        token = bond + atom_token(structure.atoms[neighbour])
        branches.append([token + below[k] for k in range(remaining)])
    for k in range(1, remaining + 1):
        children = sorted(branch[k - 1] for branch in branches)
        levels[k] = '(' + ','.join(children) + ')' if children else '()'
    return levels


def key(nucleus: str, depth: int, code: str) -> int:
    """The table's 64-bit key for a code: the shift table stores keys, not codes."""
    digest = hashlib.blake2b(f'{nucleus}|{depth}|{code}'.encode(), digest_size=8).digest()
    return int.from_bytes(digest, 'little')
