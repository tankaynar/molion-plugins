"""The SI card: the selection's HRMS line, elemental analysis and SI stub, each with Copy.

Molion draws the card from these blocks. A note is at most 200 characters and a view at most
10 blocks, so the card shows a short form of each structure; its Copy carries the full text
(at most 8000 characters).
"""

from __future__ import annotations

from si import compounds as scope
from si import elemental, hrms, stub

MAX_NOTE = 200
MAX_BLOCKS = 10
MAX_COPY = 8000


def _note(text: str, tone: str | None = None) -> dict:
    note = {'type': 'note', 'text': text if len(text) <= MAX_NOTE else text[:MAX_NOTE - 1] + '…'}
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


def _view(view_id: str, label: str, lines: list[str], problems: list[str], copy: str, caption: str) -> dict:
    blocks = [_note(line, 'muted' if line in problems else None) for line in lines]
    if len(blocks) > MAX_BLOCKS:
        blocks = blocks[:MAX_BLOCKS - 1] + [_note(f'and {len(lines) - MAX_BLOCKS + 1} more; Copy has them all', 'muted')]
    view = {'id': view_id, 'label': label, 'caption': caption, 'blocks': blocks}
    if copy:
        view['copy'] = copy
    return view


def _who(compound) -> str:
    return compound.number or stub.formula_of(compound, True) or 'Structure'


def _lines(compounds, describe, problem_types):
    """One line per compound (prefixed by which, when there are several), the problems among
    them, and what Copy takes."""
    several = len(compounds) > 1
    lines, problems, copy = [], [], []
    for compound in compounds:
        prefix = f'{_who(compound)}: ' if several else ''
        try:
            line = describe(compound.structure)
            copy.append(line)
            lines.append(prefix + line.rstrip())
        except problem_types as reason:
            lines.append(f'{prefix}{reason}')
            problems.append(lines[-1])
    return lines, problems, copy


def answer(host, params: dict) -> dict:
    """The card follows the selection only, never the adduct last copied: Molion asks it again
    when the drawing changes, so anything else it showed would be out of date until then. Its
    HRMS views are the two adducts most papers report; Copy HRMS Line… offers the rest."""
    ids = [s['moleculeId'] for s in params.get('structures') or [] if s.get('moleculeId')]
    compounds = [c for c in scope.of_molecules(host, ids) if c.structure]
    if not compounds:
        return {'message': 'Select a structure.'}

    views = []
    for adduct in (hrms.BY_ID['esi-mh'], hrms.BY_ID['esi-mna']):
        lines, problems, copy = _lines(compounds, lambda s, a=adduct: hrms.ion(s, a).line(),
                                       hrms.NotMeasurable)
        views.append(_view(adduct.id.removeprefix('esi-'), adduct.label, lines, problems, _fit(copy, '\n'),
                           'Copy HRMS Line… offers other adducts'))
    lines, problems, copy = _lines(compounds, elemental.line, elemental.NotAnalysable)
    views.append(_view('anal', 'Anal.', lines, problems, _fit(copy, '\n'), 'C, H, N and S, as combustion reports them'))

    # Names take the namer a moment; a card that waited on them would lag the selection.
    scope.with_strings(host, compounds, names=False)
    blocks = [stub.block(c, None) for c in compounds]
    # On the card, each block's first two lines: its number and formula, or formula and SMILES.
    lines = [' · '.join(block.split('\n')[:2]) for block in blocks]
    views.append(_view('stub', 'SI', lines, [], _fit(blocks, '\n\n') + '\n',
                       'Formula, SMILES and InChI; Copy SI Stub adds names and HRMS'))

    return {'subtitle': 'Calculated', 'views': views}
