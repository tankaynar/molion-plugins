"""The calculated elemental analysis an SI prints: "Anal. Calcd for C₁₅H₂₀O₃: C, 72.55; H, 8.12"."""

from __future__ import annotations

from si import formula as formulas

# What combustion analysis measures, in the order it is written.
REPORTED = ('C', 'H', 'N', 'S')


class NotAnalysable(ValueError):
    """Why a structure has no elemental analysis line."""


def line(structure: dict) -> str:
    """For an analysed structure (get-analysis). Percents to two places, as journals print them."""
    if structure.get('kind') == 'repeat-unit':
        raise NotAnalysable('a polymer is analysed per repeat unit, not as a compound')
    percents = {entry['element']: entry['percent'] for entry in structure.get('elementalAnalysis') or []}
    if not percents:
        raise NotAnalysable('; '.join(structure.get('warnings') or []) or 'it has no elemental analysis')
    reported = [f'{element}, {percents[element]:.2f}' for element in REPORTED if element in percents]
    if not reported:
        raise NotAnalysable('it has no C, H, N or S')
    counts = formulas.counts_of(structure.get('composition') or [])
    name = formulas.formula(counts) + formulas.charge_text(int(structure.get('charge') or 0))
    return f'Anal. Calcd for {name}: ' + '; '.join(reported)
