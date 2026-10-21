"""Shifts calculated with the user's own ORCA, through Molion's `calculate` (the `orca`
capability): asked about on every card, started only from the "Calculate NMR with ORCA" action.

Molion answers per molecule with a state, and once done, the server's result (`shifts_ppm`, per
atom of the calculated geometry) and `atoms`: each drawn atom's index into it, with the indices
of the hydrogens the drawing leaves implicit. A heavy atom's ¹H shift is the mean over its
hydrogens, drawn or implicit; a symmetry class's, the mean over its atoms.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .host import HostError

KIND = 'orca.nmr'
ACTION = 'calculate-orca'
BUTTON = 'Calculate NMR with ORCA'


@dataclass
class Calculation:
    state: str                                   # none, queued, running, done, failed, unavailable
    message: str | None = None
    method_line: str | None = None
    # Drawn atom id → (its own shift, its hydrogens' shifts), for a done calculation.
    shifts: dict[str, tuple[float | None, list[float]]] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.state == 'done'


def ask(host, document_id: str, molecule_id: str, start: bool = False) -> Calculation:
    if host is None:
        return Calculation('unavailable')
    try:
        reply = host.call('calculate', {'documentId': document_id, 'moleculeId': molecule_id,
                                        'kind': KIND, 'start': start})
    except HostError as error:
        # Not allowed, or a Molion that predates calculate: the card is as it always was
        return Calculation('unavailable', str(error))
    calculation = Calculation(reply.get('state') or 'unavailable', reply.get('message'), reply.get('methodLine'))
    if calculation.done:
        calculation.shifts = _shifts(reply)
        if not calculation.shifts:
            return Calculation('failed', 'The calculation returned no shifts.')
    return calculation


def _shifts(reply: dict) -> dict:
    values = (reply.get('result') or {}).get('shifts_ppm') or []

    def at(index):
        return values[index] if isinstance(index, int) and 0 <= index < len(values) else None

    shifts = {}
    for atom in reply.get('atoms') or []:
        if not atom.get('id'):
            continue
        hydrogens = [v for v in (at(h) for h in atom.get('hydrogens') or []) if v is not None]
        shifts[atom['id']] = (at(atom.get('index')), hydrogens)
    return shifts


def carbon_shift(calculation: Calculation, group) -> float | None:
    values = [calculation.shifts.get(a.id, (None, []))[0] for a in group if a.id]
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def proton_shift(calculation: Calculation, group) -> float | None:
    values = []
    for atom in group:
        if not atom.id:
            continue
        values += calculation.shifts.get(atom.id, (None, []))[1]
        # Drawn hydrogens are atoms of their own
        for hydrogen in atom.drawn_hydrogens:
            own = calculation.shifts.get(hydrogen, (None, []))[0]
            if own is not None:
                values.append(own)
    return sum(values) / len(values) if values else None
