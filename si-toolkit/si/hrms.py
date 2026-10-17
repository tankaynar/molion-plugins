"""The calculated m/z of an ion, and the HRMS line an SI prints for it.

Molion's `exactMass` is the structure as drawn: the most abundant isotope of each element (a
drawn isotope its own), with the electrons of a drawn ion allowed for. An adduct adds or takes
away atoms and electrons on top of that, with the masses below.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from si import formula as formulas

# Nuclide masses (u), AME2020, as RDKit's table has them; the electron is CODATA 2018, the
# value Molion's chemistry server subtracts for a drawn ion.
NUCLIDE = {
    'H': 1.00782503223,
    'C': 12.0,
    'N': 14.00307400443,
    'O': 15.99491461957,
    'Na': 22.9897692820,
    'Cl': 34.968852682,
    'K': 38.9637064864,
}
ELECTRON = 0.000548579909


@dataclass(frozen=True)
class Adduct:
    id: str
    ionisation: str          # what the line names in brackets: "ESI", "EI"
    label: str               # "[M+Na]⁺"
    charge: int              # of the ion
    atoms: dict = field(default_factory=dict)   # atoms added (negative: taken away)
    keywords: str = ''

    def mass_change(self) -> float:
        return sum(NUCLIDE[element] * n for element, n in self.atoms.items())


ADDUCTS = [
    Adduct('esi-mh', 'ESI', '[M+H]⁺', +1, {'H': 1}, 'positive proton protonated'),
    Adduct('esi-mna', 'ESI', '[M+Na]⁺', +1, {'Na': 1}, 'positive sodium'),
    Adduct('esi-mk', 'ESI', '[M+K]⁺', +1, {'K': 1}, 'positive potassium'),
    Adduct('esi-mnh4', 'ESI', '[M+NH₄]⁺', +1, {'N': 1, 'H': 4}, 'positive ammonium nh4'),
    Adduct('esi-m-h', 'ESI', '[M−H]⁻', -1, {'H': -1}, 'negative deprotonated'),
    Adduct('esi-mcl', 'ESI', '[M+Cl]⁻', -1, {'Cl': 1}, 'negative chloride'),
    Adduct('apci-mh', 'APCI', '[M+H]⁺', +1, {'H': 1}, 'positive proton protonated'),
    Adduct('ei-m', 'EI', 'M⁺·', +1, {}, 'positive radical cation electron impact'),
]
BY_ID = {adduct.id: adduct for adduct in ADDUCTS}
DEFAULT = 'esi-mh'


@dataclass(frozen=True)
class Ion:
    ionisation: str
    label: str
    formula: str            # with subscripts, without the charge: "C₁₅H₂₀NaO₃"
    plain_formula: str      # "C15H20NaO3"
    mz: float

    def line(self) -> str:
        return f'HRMS ({self.ionisation}) m/z: {self.label} calcd for {self.formula} {self.mz:.4f}, found '


class NotMeasurable(ValueError):
    """Why a structure has no HRMS line."""


def ion(structure: dict, adduct: Adduct) -> Ion:
    """The ion an analysed structure (get-analysis) gives with this adduct.

    A structure drawn as an ion is measured as it is ("[M]⁺"), whatever adduct was chosen:
    adding a proton to a cation is not what anyone means.
    """
    if structure.get('kind') == 'repeat-unit':
        raise NotMeasurable('a polymer has no single mass')
    if structure.get('exactMass') is None:
        raise NotMeasurable('; '.join(structure.get('warnings') or []) or 'it has no exact mass')

    counts = formulas.counts_of(structure.get('composition') or [])
    charge = int(structure.get('charge') or 0)
    if charge != 0:
        label = '[M]' + formulas.charge_text(charge)
        return Ion(adduct.ionisation, label,
                   formulas.formula(counts), formulas.formula(counts, unicode=False),
                   structure['exactMass'] / abs(charge))

    if any(counts.get((element, 0), 0) + n < 0 for element, n in adduct.atoms.items()):
        raise NotMeasurable(f'it has no atoms to lose for {adduct.label}')

    ion_counts = formulas.with_atoms(counts, adduct.atoms)
    # Each unit of positive charge is an electron gone; of negative, one gained.
    mass = structure['exactMass'] + adduct.mass_change() - adduct.charge * ELECTRON
    return Ion(adduct.ionisation, adduct.label, formulas.formula(ion_counts),
               formulas.formula(ion_counts, unicode=False), mass / abs(adduct.charge))
