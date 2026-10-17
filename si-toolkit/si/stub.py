"""The SI stub: for every compound, what its characterisation paragraph starts from.

As text for Word, one block per compound:

    3a: (2S)-2-[4-(2-methylpropyl)phenyl]propanoic acid
    C₁₃H₁₈O₂; HRMS (ESI) m/z: [M+H]⁺ calcd for C₁₃H₁₉O₂ 207.1380, found
    SMILES: CC(C)Cc1ccc(cc1)[C@H](C)C(=O)O
    InChI: InChI=1S/…

and as CSV, one row per compound, for a spreadsheet or an ELN.
"""

from __future__ import annotations

import csv
import io

from si import formula as formulas
from si import hrms
from si.compounds import Compound


def formula_of(compound: Compound, unicode: bool) -> str:
    structure = compound.structure or {}
    if not structure.get('composition'):
        return structure.get('formula') or ''
    counts = formulas.counts_of(structure['composition'])
    charge = int(structure.get('charge') or 0)
    if unicode:
        return formulas.formula(counts) + formulas.charge_text(charge)
    return formulas.formula(counts, unicode=False) + ('' if charge == 0 else
                                                      (str(abs(charge)) if abs(charge) > 1 else '') + ('+' if charge > 0 else '-'))


def _ion(compound: Compound, adduct: hrms.Adduct) -> hrms.Ion | None:
    try:
        return hrms.ion(compound.structure, adduct) if compound.structure else None
    except hrms.NotMeasurable:
        return None


def heading(compound: Compound) -> str:
    """"3a: name", "3a", or the name alone; nothing when there is neither (the formula line
    that follows says what it is)."""
    return ': '.join(p for p in (compound.number, compound.name) if p)


def block(compound: Compound, adduct: hrms.Adduct | None) -> str:
    """Without an adduct, no HRMS line (the card shows HRMS in views of its own)."""
    lines = [heading(compound)]
    ion = _ion(compound, adduct) if adduct else None
    formula = formula_of(compound, True)
    lines.append('; '.join(p for p in (formula, ion.line().rstrip() if ion else None) if p))
    if compound.smiles:
        lines.append(f'SMILES: {compound.smiles}')
    if compound.inchi:
        lines.append(f'InChI: {compound.inchi}')
    return '\n'.join(line for line in lines if line)


def text(compounds: list[Compound], adduct: hrms.Adduct) -> str:
    return '\n\n'.join(block(c, adduct) for c in compounds) + '\n'


CSV_HEADER = ['number', 'name', 'formula', 'ionisation', 'adduct', 'mz', 'smiles', 'inchi']


def csv_text(compounds: list[Compound], adduct: hrms.Adduct) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(CSV_HEADER)
    for compound in compounds:
        ion = _ion(compound, adduct)
        writer.writerow([compound.number or '', compound.name or '', formula_of(compound, False),
                         ion.ionisation if ion else '', ion.label if ion else '',
                         f'{ion.mz:.4f}' if ion else '', compound.smiles or '', compound.inchi or ''])
    return out.getvalue()
