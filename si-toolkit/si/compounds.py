"""What the SI is written about: the drawing's molecules with their compound numbers, analyses and names."""

from __future__ import annotations

from dataclasses import dataclass

from si import numbers
from si.rpc import HostError, log


@dataclass
class Compound:
    molecule_id: str
    number: str | None = None
    structure: dict | None = None      # get-analysis, the whole molecule
    name: str | None = None
    smiles: str | None = None
    inchi: str | None = None
    name_error: str | None = None      # why there is no name: the namer refused, or could not run


def _molecules(host) -> list[dict]:
    molecules = host.scene('get-molecules')
    return [m for m in molecules if m.get('atoms')] if isinstance(molecules, list) else []


def _number(molecule: dict) -> str | None:
    number = molecule.get('number') or {}
    return number.get('text') if number.get('mode') != 'off' else None


def selected(host) -> list[Compound]:
    """The molecules the selection touches, whole; every molecule when nothing is selected."""
    molecules = _molecules(host)
    selection = host.scene('get-selection') or {}
    atoms, bonds = set(selection.get('atoms') or []), set(selection.get('bonds') or [])
    touched = [m for m in molecules
               if atoms & {a['id'] for a in m['atoms']} or bonds & {b['id'] for b in m.get('bonds') or []}]
    return analysed(host, [Compound(m['id'], _number(m)) for m in (touched or molecules)])


def everything(host) -> list[Compound]:
    """Every molecule, numbered ones first in number order (one entry per number: the same
    structure drawn twice shares it), then the rest as drawn."""
    molecules = _molecules(host)
    numbered = [m for m in molecules if _number(m)]
    key = numbers.sort_key_for([_number(m) for m in numbered])
    seen, ordered = set(), []
    for molecule in sorted(numbered, key=lambda m: key(_number(m))):
        if _number(molecule) not in seen:
            seen.add(_number(molecule))
            ordered.append(molecule)
    ordered += [m for m in molecules if not _number(m)]
    return analysed(host, [Compound(m['id'], _number(m)) for m in ordered])


def of_molecules(host, molecule_ids: list[str]) -> list[Compound]:
    """For a card: the molecules it was sent, with the numbers the drawing gives them."""
    by_id = {m['id']: m for m in _molecules(host)}
    return analysed(host, [Compound(i, _number(by_id[i]) if i in by_id else None)
                           for i in dict.fromkeys(molecule_ids)])


def analysed(host, compounds: list[Compound]) -> list[Compound]:
    if not compounds:
        return compounds
    answer = host.scene('get-analysis', moleculeIds=[c.molecule_id for c in compounds])
    whole = {}
    for structure in answer.get('structures') or []:
        # A polymer comes back per repeat unit; its first one says why it has no mass.
        if structure.get('kind') == 'whole' or structure['moleculeId'] not in whole:
            whole[structure['moleculeId']] = structure
    for compound in compounds:
        compound.structure = whole.get(compound.molecule_id)
    return compounds


def with_strings(host, compounds: list[Compound], names: bool = True) -> list[Compound]:
    """SMILES, InChI and, where one can be made on this machine, the name."""
    if not compounds:
        return compounds
    ids = [c.molecule_id for c in compounds]
    targets = ['smiles', 'inchi'] + (['name'] if names else [])
    refused = None
    try:
        answer = host.scene('get-strings', targets=targets, moleculeIds=ids)
    except HostError as error:
        if not names:
            raise
        # No namer (OPSIN missing): the rest is still worth having.
        log(f'names unavailable: {error}')
        refused = str(error)
        answer = host.scene('get-strings', targets=['smiles', 'inchi'], moleculeIds=ids)
    strings = {m['moleculeId']: m for m in answer.get('molecules') or []}
    for compound in compounds:
        found = strings.get(compound.molecule_id) or {}
        compound.smiles, compound.inchi, compound.name = found.get('smiles'), found.get('inchi'), found.get('name')
        compound.name_error = (found.get('nameError') or found.get('error') or refused) if names else None
    return compounds


def why_unnamed(compounds: list[Compound]) -> str | None:
    """When no compound got a name, why: most often the namer cannot run on this machine."""
    if not compounds or any(c.name for c in compounds):
        return None
    return next((c.name_error for c in compounds if c.name_error), None)
