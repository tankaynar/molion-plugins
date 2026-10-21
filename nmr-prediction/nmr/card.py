"""The card Molion shows: a ¹H and a ¹³C view, each a stick spectrum whose peaks are linked
to the atoms they come from, with an SI-style line to copy.

One peak per set of equivalent atoms (a symmetry class), so para-substituted benzene has two
aromatic ¹H peaks of 2H each, as it is reported. With part of a molecule selected (`focus`),
only its peaks are shown, predicted from the whole molecule's surroundings.

Where the user has calculated a molecule's shifts with ORCA (calculated.py), its peaks are at
the calculated shifts instead, and the card says by which method; where they have not, and ORCA
is set up, it offers to.
"""

from __future__ import annotations

from collections import defaultdict

from . import calculated, multiplets, predict
from .structure import read

SUBSCRIPTS = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
# The shift table is derived from nmrshiftdb2, whose licence the plugin honours (NOTICE);
# every card says where its numbers come from.
DATA_NOTE = 'Shifts from measured data in nmrshiftdb2 (nmrshiftdb.org).'

def answer(params: dict, table, host=None) -> dict:
    structures = [read(entry) for entry in params.get('structures') or []]
    if not structures:
        return {'message': 'Select a structure.'}
    # The whole document is several things: a scheme, a reaction. Ask which.
    if params.get('scope') == 'document' and len(structures) > 1:
        return {'message': 'Select a structure to predict its spectra.'}
    usable = [s for s in structures if not s.error]
    if not usable:
        return {'message': f"Can't predict: {structures[0].error}"}

    document_id = params.get('documentId') or ''
    calculations = [calculated.ask(host, document_id, s.molecule_id) if host and s.molecule_id
                    else calculated.Calculation('unavailable') for s in usable]

    proton, carbon = [], []
    rough = unknown = missing = 0
    for number, (structure, calculation) in enumerate(zip(usable, calculations)):
        if any(a.element == '*' for a in structure.atoms):
            unknown += 1
        for peaks, make, atoms in ((proton, _proton_peak, predict.protonated(structure)),
                                   (carbon, _carbon_peak, predict.carbons(structure))):
            for group in _groups(structure, atoms):
                peak = make(table, structure, number, group, calculation)
                if peak is None:
                    missing += 1
                    continue
                rough += peak.pop('_rough')
                peaks.append(peak)

    if not proton and not carbon:
        return {'message': 'Nothing to predict here: select carbons or atoms with hydrogens.'}

    notes = []
    for calculation in calculations:
        if calculation.state == 'failed':
            notes.append({'type': 'note', 'tone': 'warning',
                          'text': f'ORCA could not calculate the shifts: {calculation.message or "it failed"}'})
            break
    if rough:
        notes.append({'type': 'note', 'tone': 'warning',
                      'text': f'{rough} shift{"s are" if rough > 1 else " is"} rough: '
                              'database has little with surroundings like '
                              f'{"theirs" if rough > 1 else "its"}.'})
    if missing:
        notes.append({'type': 'note', 'tone': 'warning',
                      'text': f'{missing} signal{"s have" if missing > 1 else " has"} no prediction.'})
    if unknown:
        notes.append({'type': 'note', 'text': 'Groups without a structure (R, X…) are not predicted.'})
    method_lines = list(dict.fromkeys(c.method_line for c in calculations if c.done and c.method_line))
    if method_lines:
        notes.append({'type': 'note', 'text': 'Calculated with ' + '; '.join(method_lines) + '.'})
    if any(not p['_calculated'] for p in proton + carbon):
        notes.append({'type': 'note', 'text': DATA_NOTE})
    # Running or queued, Molion shows the job's progress (and Cancel) in the card itself
    if any(c.state in ('none', 'failed') for c in calculations):
        notes.append({'type': 'button', 'label': calculated.BUTTON, 'action': calculated.ACTION})

    done = sum(c.done for c in calculations)
    return {
        'subtitle': 'Calculated' if done == len(calculations) else 'Predicted and calculated' if done else 'Predicted',
        'views': [
            _view('1h', '¹H', proton, 'δ (ppm)', (0, 10), _proton_copy(proton), notes),
            _view('13c', '¹³C', carbon, 'δ (ppm)', (0, 200), _carbon_copy(carbon), notes),
        ],
    }


def _groups(structure, atoms):
    """Atoms by symmetry class, in the order they come, the selected ones only."""
    by_class = defaultdict(list)
    for atom in atoms:
        by_class[atom.symmetry_class].append(atom)
    return [group for group in by_class.values() if any(structure.in_focus(a) for a in group)]


def _linked(group) -> list[str]:
    seen = []
    for atom in group:
        for atom_id in atom.drawn_ids:
            if atom_id not in seen:
                seen.append(atom_id)
    return seen


def _shift(table, structure, group, nucleus, calculation, of_calculation):
    """(value, readout suffix, rough, calculated): the calculated shift where there is one, else
    the predicted one, said so when the rest of a calculated molecule's peaks are calculated."""
    if calculation is not None and calculation.done:
        value = of_calculation(calculation, group)
        if value is not None:
            return value, '', False, True
    shift = predict.shift_of(table, structure, group[0].index, nucleus)
    if shift is None:
        return None
    suffix = _certainty(shift) + (' · predicted' if calculation is not None and calculation.done else '')
    return shift.value, suffix, shift.rough, False


def _proton_peak(table, structure, number, group, calculation=None):
    atom = group[0]
    shift = _shift(table, structure, group, predict.PROTON, calculation, calculated.proton_shift)
    if shift is None:
        return None
    value, suffix, rough, is_calculated = shift
    hydrogens = sum(a.hydrogens for a in group)
    split = multiplets.multiplet_of(structure, atom)
    j = split.j_text
    readout = f'{value:.2f} · {split.name}' + (f', J = {j} Hz' if j else '') + f' · {hydrogens}H' + suffix
    return {
        'link': f'h{number}-{atom.symmetry_class}',
        'position': round(value, 3),
        'height': hydrogens,
        'lines': [[round(value + offset, 5), round(intensity * hydrogens, 4)]
                  for offset, intensity in split.lines] if len(split.lines) > 1 else [],
        'readout': readout,
        'atoms': _linked(group),
        '_rough': 1 if rough else 0,
        '_calculated': is_calculated,
        '_copy': (value, split, hydrogens),
    }


def _carbon_peak(table, structure, number, group, calculation=None):
    atom = group[0]
    shift = _shift(table, structure, group, predict.CARBON, calculation, calculated.carbon_shift)
    if shift is None:
        return None
    value, suffix, rough, is_calculated = shift
    kind = 'C' if atom.hydrogens == 0 else 'CH' if atom.hydrogens == 1 else f'CH{atom.hydrogens}'.translate(SUBSCRIPTS)
    readout = f'{value:.1f} · {kind}' + (f' · {len(group)}C' if len(group) > 1 else '') + suffix
    return {
        'link': f'c{number}-{atom.symmetry_class}',
        'position': round(value, 2),
        'height': len(group),
        'readout': readout,
        'atoms': _linked(group),
        '_rough': 1 if rough else 0,
        '_calculated': is_calculated,
        '_copy': value,
    }


def _certainty(shift) -> str:
    if shift.rough:
        return ' · rough'
    return f' · ±{shift.spread:.2f}' if shift.count >= 3 and shift.spread > 0 else ''


def _view(view_id, label, peaks, axis_label, default, copy, notes) -> dict:
    positions = [p['position'] for p in peaks]
    low = min([default[0]] + [p - (0.5 if view_id == '1h' else 5) for p in positions])
    high = max([default[1]] + [p + (0.5 if view_id == '1h' else 5) for p in positions])
    for peak in peaks:
        peak.pop('_copy', None)
        peak.pop('_calculated', None)
    blocks = [{'type': 'spectrum',
               'axis': {'label': axis_label, 'min': round(low, 1), 'max': round(high, 1), 'reversed': True},
               'peaks': peaks}]
    return {
        'id': view_id,
        'label': label,
        'caption': f'{len(peaks)} signal{"s" if len(peaks) != 1 else ""}' if peaks else 'No signals',
        'copy': copy,
        'blocks': blocks + notes,
    }


def _proton_copy(peaks) -> str | None:
    """¹H NMR (400 MHz, predicted) δ 7.26 (d, J = 8.0 Hz, 2H), …: highest shift first."""
    if not peaks:
        return None
    parts = []
    for value, split, hydrogens in sorted((p['_copy'] for p in peaks), key=lambda c: -c[0]):
        j = split.j_text
        parts.append(f'{value:.2f} ({split.name}' + (f', J = {j} Hz' if j else '') + f', {hydrogens}H)')
    return f'¹H NMR ({multiplets.FREQUENCY:.0f} MHz, {_source(peaks)}) δ ' + ', '.join(parts) + '.'


def _carbon_copy(peaks) -> str | None:
    if not peaks:
        return None
    values = sorted((p['_copy'] for p in peaks), reverse=True)
    return (f'¹³C NMR ({multiplets.CARBON_FREQUENCY:.0f} MHz, {_source(peaks)}) δ '
            + ', '.join(f'{v:.1f}' for v in values) + '.')


def _source(peaks) -> str:
    """What the copied line says its shifts are: never "calculated" for a predicted one."""
    calculated_peaks = sum(1 for p in peaks if p.get('_calculated'))
    return ('calculated' if calculated_peaks == len(peaks)
            else 'predicted and calculated' if calculated_peaks else 'predicted')
