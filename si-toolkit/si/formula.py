"""Formulas as an SI writes them, from the composition Molion's analysis reports.

Molion's own `formula` is plain Hill text ("C13H18O2"). An HRMS line names the ion, so the
adduct's atoms have to be added first, and journals set the counts as subscripts. Both are
done here from `composition` ({element, isotope, count}; isotope 0 for the natural element).
"""

from __future__ import annotations

SUBSCRIPTS = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
SUPERSCRIPTS = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')

# Hydrogen's isotopes keep their own symbols, as Molion's formula writes them.
HYDROGEN_ISOTOPES = {2: 'D', 3: 'T'}

Counts = dict  # (element, isotope) -> count


def counts_of(composition: list[dict]) -> Counts:
    counts: Counts = {}
    for entry in composition:
        key = (entry['element'], int(entry.get('isotope') or 0))
        counts[key] = counts.get(key, 0) + int(entry['count'])
    return counts


def with_atoms(counts: Counts, change: dict[str, int]) -> Counts:
    """`counts` with natural atoms added (or taken away, for a negative count)."""
    result = dict(counts)
    for element, n in change.items():
        key = (element, 0)
        result[key] = result.get(key, 0) + n
        if result[key] == 0:
            del result[key]
    return result


def hill_order(elements) -> list[str]:
    """C, then H, then the rest alphabetically; without carbon, all alphabetically."""
    elements = set(elements)
    if 'C' in elements:
        return ['C'] + (['H'] if 'H' in elements else []) + sorted(elements - {'C', 'H'})
    return sorted(elements)


def _symbol(element: str, isotope: int, unicode: bool) -> str:
    if not isotope:
        return element
    if element == 'H' and isotope in HYDROGEN_ISOTOPES:
        return HYDROGEN_ISOTOPES[isotope]
    return str(isotope).translate(SUPERSCRIPTS) + element if unicode else f'[{isotope}{element}]'


def formula(counts: Counts, unicode: bool = True) -> str:
    """Hill order, the natural element before its isotopes: "C₁₃H₁₈O₂", or "C13H18O2" plain."""
    parts = []
    for element in hill_order(e for e, _ in counts):
        for isotope in sorted(i for e, i in counts if e == element):
            n = counts[(element, isotope)]
            if n <= 0:
                continue
            count = '' if n == 1 else str(n)
            parts.append(_symbol(element, isotope, unicode) + (count.translate(SUBSCRIPTS) if unicode else count))
    return ''.join(parts)


def charge_text(charge: int) -> str:
    """"⁺", "²⁻", or "" for a neutral species."""
    if charge == 0:
        return ''
    sign = '⁺' if charge > 0 else '⁻'
    size = abs(charge)
    return (str(size).translate(SUPERSCRIPTS) if size > 1 else '') + sign
