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
    return compound.number or (compound.structure or {}).get('formula') or 'Structure'


def answer(host, settings, params: dict) -> dict:
    ids = [s['moleculeId'] for s in params.get('structures') or [] if s.get('moleculeId')]
    compounds = [c for c in scope.of_molecules(host, ids) if c.structure]
    if not compounds:
        return {'message': 'Select a structure.'}
    adduct = settings.adduct
    several = len(compounds) > 1

    hrms_lines, hrms_problems, hrms_copy = [], [], []
    ea_lines, ea_problems, ea_copy = [], [], []
    for compound in compounds:
        prefix = f'{_who(compound)}: ' if several else ''
        try:
            line = hrms.ion(compound.structure, adduct).line()
            hrms_copy.append(line)
            hrms_lines.append(prefix + line.rstrip())
        except hrms.NotMeasurable as reason:
            hrms_lines.append(f'{prefix}no m/z: {reason}')
            hrms_problems.append(hrms_lines[-1])
        try:
            line = elemental.line(compound.structure)
            ea_copy.append(line)
            ea_lines.append(prefix + line)
        except elemental.NotAnalysable as reason:
            ea_lines.append(f'{prefix}no analysis: {reason}')
            ea_problems.append(ea_lines[-1])

    # Names take the namer a moment; a card that waited on them would lag the selection.
    scope.with_strings(host, compounds, names=False)
    stub_blocks = [stub.block(c, adduct) for c in compounds]
    # On the card, each block's heading and its formula-and-HRMS line.
    stub_lines = [' · '.join(block.split('\n')[:2]) for block in stub_blocks]

    return {
        'subtitle': f'Calculated · {adduct.ionisation} {adduct.label}',
        'views': [
            _view('hrms', 'HRMS', hrms_lines, hrms_problems, _fit(hrms_copy, '\n'),
                  'Copy HRMS Line… chooses another adduct'),
            _view('anal', 'Anal.', ea_lines, ea_problems, _fit(ea_copy, '\n'), 'C, H, N and S, as combustion reports them'),
            _view('stub', 'SI', stub_lines, [], _fit(stub_blocks, '\n\n') + '\n',
                  'Formula, HRMS, SMILES and InChI; Copy SI Stub adds names'),
        ],
    }
