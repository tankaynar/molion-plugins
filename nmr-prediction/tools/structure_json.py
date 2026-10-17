"""An RDKit molecule as Molion describes a structure to plugins (the `structures` of a card
request): what tools/build_table.py turns nmrshiftdb2's molecules into, so that codes are
computed from the very same description at build time and in Molion.

Molion perceives structures with RDKit 2025.9.2 and these rules: RDKit's default aromaticity,
total hydrogens including drawn H atoms, rings, and topological symmetry classes. Only what
HOSE codes and multiplets read has to agree.
"""

from __future__ import annotations

from rdkit import Chem

_HYBRIDIZATION = {
    Chem.HybridizationType.S: 's',
    Chem.HybridizationType.SP: 'sp',
    Chem.HybridizationType.SP2: 'sp2',
    Chem.HybridizationType.SP3: 'sp3',
    Chem.HybridizationType.SP3D: 'sp3d',
    Chem.HybridizationType.SP3D2: 'sp3d2',
}

_ORDER = {
    Chem.BondType.SINGLE: 1,
    Chem.BondType.DOUBLE: 2,
    Chem.BondType.TRIPLE: 3,
    Chem.BondType.QUADRUPLE: 4,
    Chem.BondType.AROMATIC: 1.5,
}


def describe(mol, molecule_id: str = 'm') -> dict:
    """A sanitised molecule → {moleculeId, focus, atoms, bonds}, atoms in the molecule's order.

    Double-bond geometry is read from 2D coordinates, as Molion reads a drawing; a molecule
    without them (from SMILES) is laid out first.
    """
    if mol.GetNumConformers() == 0:
        from rdkit.Chem import rdDepictor
        mol = Chem.Mol(mol)
        rdDepictor.Compute2DCoords(mol)
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    rings = mol.GetRingInfo()
    classes = list(Chem.CanonicalRankAtoms(mol, breakTies=False))
    atoms = []
    for atom in mol.GetAtoms():
        i = atom.GetIdx()
        atoms.append({
            'id': f'a{i}',
            'element': atom.GetSymbol() if atom.GetAtomicNum() > 0 else '*',
            'charge': atom.GetFormalCharge(),
            'isotope': atom.GetIsotope() or None,
            'radical': atom.GetNumRadicalElectrons(),
            'hydrogens': atom.GetTotalNumHs(includeNeighbors=True),
            'aromatic': atom.GetIsAromatic(),
            'inRing': atom.IsInRing(),
            'ringSizes': sorted(rings.AtomRingSizes(i)),
            'hybridization': _HYBRIDIZATION.get(atom.GetHybridization()),
            'symmetryClass': int(classes[i]),
        })
    bonds = [{
        'atoms': [b.GetBeginAtomIdx(), b.GetEndAtomIdx()],
        'order': _ORDER.get(b.GetBondType(), 1),
        'aromatic': b.GetIsAromatic(),
        'inRing': b.IsInRing(),
        'stereo': _stereo(mol, b),
    } for b in mol.GetBonds()]
    return {'moleculeId': molecule_id, 'focus': None, 'atoms': atoms, 'bonds': bonds}


_DEFINED = {Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ,
            Chem.BondStereo.STEREOCIS, Chem.BondStereo.STEREOTRANS}


def _stereo(mol, bond):
    """{relation: cis|trans, atoms}, 'either' or None, from where the atoms lie."""
    if bond.GetBondType() != Chem.BondType.DOUBLE:
        return None
    if bond.GetStereo() == Chem.BondStereo.STEREOANY:
        return 'either'
    reference = list(bond.GetStereoAtoms())
    if bond.GetStereo() not in _DEFINED or len(reference) != 2 or mol.GetNumConformers() == 0:
        return None
    begin, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
    first, second = reference
    if mol.GetBondBetweenAtoms(first, begin) is None:
        first, second = second, first
    position = mol.GetConformer().GetAtomPosition

    def side(point):
        a, b = position(begin), position(end)
        cross = (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x)
        return 0 if abs(cross) < 1e-6 else (1 if cross > 0 else -1)

    one, other = side(position(first)), side(position(second))
    if one == 0 or other == 0:
        return None
    return {'relation': 'cis' if one == other else 'trans', 'atoms': [first, second]}
