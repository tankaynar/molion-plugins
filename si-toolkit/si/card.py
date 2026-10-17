"""The SI card: the selection's HRMS line, elemental analysis and SI stub, each with Copy.

Molion draws the card from these blocks: each structure a labelled note (its number, else its
formula, bold at the left). A note is at most 200 characters and a view at most 10 blocks, so
the card shows a short form of each structure; its Copy carries the full text (at most 8000
characters).
"""

from __future__ import annotations

from si import compounds as scope
from si import elemental, hrms, numbers, stub

MAX_NOTE = 200
MAX_BLOCKS = 10
MAX_COPY = 8000
MAX_LABEL = 40


def _note(text: str, label: str | None = None, tone: str | None = None) -> dict:
    note = {'type': 'note', 'text': text if len(text) <= MAX_NOTE else text[:MAX_NOTE - 1] + '…'}
    if label:
        note['label'] = label[:MAX_LABEL]
    if tone:
        note['tone'] = tone
    return note


def _fit(texts: list[str], separator: str) -> str:
    """As many whole entries as fit the clipboard limit."""
    kept, size = [], 0
    for text in texts:
        size += len(text) + (len(separator) if kept else 0)
        if size > MAX_COPY:
            break
        kept.append(text)
    return separator.join(kept)


def _view(view_id: str, label: str, rows: list[dict], copy: str) -> dict:
    """Rows are labelled notes, one a structure; past the block limit, a note says how many more."""
    if len(rows) > MAX_BLOCKS:
        rows = rows[:MAX_BLOCKS - 1] + [_note(f'and {len(rows) - MAX_BLOCKS + 1} more; Copy has them all')]
    view = {'id': view_id, 'label': label, 'blocks': rows}
    if copy:
        view['copy'] = copy
    return view


def _who(compound) -> str:
    """A structure's label on the card: its number, else its formula."""
    return compound.number or stub.formula_of(compound, True) or 'Structure'


def _rows(compounds, describe, problem_types):
    """A labelled row per compound, and what Copy takes. A structure with no line says why,
    as a warning."""
    rows, copy = [], []
    for compound in compounds:
        try:
            line = describe(compound.structure)
            copy.append(line)
            rows.append(_note(line.rstrip().removesuffix(', found'), _who(compound)))
        except problem_types as reason:
            rows.append(_note(str(reason).capitalize(), _who(compound), 'warning'))
    return rows, copy


def _stub_row(compound) -> dict:
    """The number's row reads "C₁₃H₁₈O₂ · SMILES"; a formula's, the SMILES alone."""
    formula = stub.formula_of(compound, True)
    parts = [formula] if compound.number and formula else []
    parts.append(compound.smiles or 'no SMILES')
    return _note(' · '.join(parts), _who(compound))


def answer(host, params: dict) -> dict:
    """The card follows the selection only, never the adduct last copied: Molion asks it again
    when the drawing changes, so anything else it showed would be out of date until then. Its
    HRMS views are the two adducts most papers report; Copy HRMS Line… offers the rest."""
    ids = [s['moleculeId'] for s in params.get('structures') or [] if s.get('moleculeId')]
    compounds = [c for c in scope.of_molecules(host, ids) if c.structure]
    if not compounds:
        return {'message': 'Select a structure.'}
    # Numbered first, in number order, as the SI lists them; the rest as Molion sent them.
    key = numbers.sort_key_for([c.number for c in compounds if c.number])
    compounds.sort(key=lambda c: (0, key(c.number)) if c.number else (1, (0, 0, '')))

    views = []
    for adduct in (hrms.BY_ID['esi-mh'], hrms.BY_ID['esi-mna']):
        rows, copy = _rows(compounds, lambda s, a=adduct: hrms.ion(s, a).line(), hrms.NotMeasurable)
        views.append(_view(adduct.id.removeprefix('esi-'), adduct.label, rows, _fit(copy, '\n')))
    rows, copy = _rows(compounds, elemental.line, elemental.NotAnalysable)
    views.append(_view('anal', 'Anal.', rows, _fit(copy, '\n')))

    # Names take the namer a moment; a card that waited on them would lag the selection.
    scope.with_strings(host, compounds, names=False)
    blocks = [stub.block(c, None) for c in compounds]
    views.append(_view('stub', 'SI', [_stub_row(c) for c in compounds], _fit(blocks, '\n\n') + '\n'))

    count = len(compounds)
    return {'subtitle': 'Calculated' if count == 1 else f'Calculated for {count} structures', 'views': views}
