#!/usr/bin/env python3
"""Measures Picture to Structure on labelled pictures. Maintainers only.

    python evaluate.py --bench real/ --molscribe-src MolScribe/ \
        --model int8=out/ --model fp32=out-fp32/ [--sets acs,CLEF] [--sample 150] \
        [--variants plain,jpeg40,half] [--white 245] --results results.jsonl

--bench is MolScribe's real.zip unpacked (huggingface.co/yujieq/MolScribe): a CSV per set
(image_id, file_path, SMILES) and the pictures. ACS is cut from journal articles; CLEF, UOB and
USPTO from patents and catalogues; Staker is low resolution.

Each picture goes through the plugin's own path, picture → Structure → molfile, and the
molfile is read back with RDKit (its abbreviations expanded by MolScribe's rules, standing in for
the app's) and scored as MolScribe's evaluator scores: canonical SMILES ignoring
cis/trans ("exact"), ignoring stereo too ("graph"), and on the molecules with stereocentres
("stereo"). As a reference, the same model output is also put through MolScribe's own RDKit
post-processing ("upstream"), which separates what the model gets wrong from what the
plugin's molfile and wedge rule do.

Variants: `plain`, `jpeg40` (JPEG at quality 40), `half` (half the size, then JPEG 75), the
damage a picture taken from a PDF screenshot or a web page tends to have.

Every picture's result is a line in --results; the summary is printed at the end and can be
printed again from the file with --summarise.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import statistics
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

SETS = ('acs', 'CLEF', 'UOB', 'USPTO', 'staker')


def damaged(data: bytes, variant: str) -> bytes:
    if variant == 'plain':
        return data
    from PIL import Image
    image = Image.open(io.BytesIO(data)).convert('RGB')
    if variant == 'half':
        image = image.resize((max(1, image.width // 2), max(1, image.height // 2)), Image.BILINEAR)
        quality = 75
    elif variant == 'jpeg40':
        quality = 40
    else:
        raise SystemExit(f'unknown variant {variant}')
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=quality)
    return out.getvalue()


class Scorer:
    """MolScribe's canonicalisation and abbreviation expansion, from its own source."""

    def __init__(self, molscribe_src: str) -> None:
        import molscribe_loader
        molscribe_loader._register_package('molscribe', os.path.join(molscribe_src, 'molscribe'))
        from rdkit import RDLogger
        RDLogger.DisableLog('rdApp.*')
        from molscribe import chemistry, evaluate
        self.chemistry, self.evaluate = chemistry, evaluate
        # Upstream's expansion passes each attachment's bond order through the atoms' radical
        # counts, which current RDKit resets on the way; every abbreviation then failed. Same
        # rules, the orders kept in a dict.
        chemistry._expand_functional_group = self._expand

    def _expand(self, mol, mappings, debug=False):
        from rdkit import Chem
        chemistry = self.chemistry
        orders = {1.0: Chem.BondType.SINGLE, 2.0: Chem.BondType.DOUBLE, 3.0: Chem.BondType.TRIPLE}
        mol_w = Chem.RWMol(mol)
        remove = []
        for index in range(mol.GetNumAtoms()):
            atom = mol_w.GetAtomWithIdx(index)
            symbol = Chem.GetAtomAlias(atom) if atom.GetAtomicNum() == 0 else ''
            if not symbol or symbol in chemistry.RGROUP_SYMBOLS:
                continue
            bonds = list(atom.GetBonds())
            sub = chemistry.get_smiles_from_symbol(symbol, mol_w, atom, bonds)
            fragment = Chem.MolFromSmiles(sub) if sub else None
            if fragment is None:
                continue
            links = [(b.GetOtherAtomIdx(index), orders.get(b.GetBondTypeAsDouble(), Chem.BondType.SINGLE))
                     for b in bonds]
            for other, _ in links:
                mol_w.RemoveBond(index, other)
            start = mol_w.GetNumAtoms()
            mol_w = Chem.RWMol(Chem.CombineMols(mol_w, fragment))
            for other, order in links:
                mol_w.AddBond(other, start, order)
            for i in range(start, mol_w.GetNumAtoms()):
                mol_w.GetAtomWithIdx(i).SetNumRadicalElectrons(0)
            remove.append(index)
        for index in sorted(remove, reverse=True):
            mol_w.RemoveAtom(index)
        result = mol_w.GetMol()
        Chem.SanitizeMol(result)
        return Chem.MolToSmiles(result), result

    def canon(self, smiles: str, ignore_chiral: bool) -> str:
        # The gold writes aryl as [Ar], which RDKit takes for argon; score it as any substituent.
        smiles = smiles.replace('[Ar]', '*')
        canon, ok = self.evaluate.canonicalize_smiles(smiles, ignore_chiral=ignore_chiral, ignore_cistrans=True)
        return canon if ok else '<invalid>'

    def from_molfile(self, text: str) -> str:
        """The plugin's molfile as Molion would hold it: wedges read for stereo, aliases expanded."""
        from rdkit import Chem
        mol = Chem.MolFromMolBlock(text, sanitize=False)
        if mol is None:
            return ''
        for atom in mol.GetAtoms():
            if atom.HasProp('molFileAlias'):
                alias = atom.GetProp('molFileAlias')
                atom.SetAtomicNum(0)
                atom.SetNoImplicit(True)
                Chem.SetAtomAlias(atom, alias)
                if alias[:1] == 'R' and alias[1:].isdigit():
                    atom.SetIsotope(int(alias[1:]))    # R1 → [1*], as the gold is canonicalised
        try:
            Chem.SanitizeMol(mol)
            Chem.AssignChiralTypesFromBondDirs(mol)
            Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
            smiles, _ = self._expand(mol, {})
            return smiles
        except Exception:
            return ''

    def upstream(self, reading) -> str:
        if not reading.symbols:
            return ''
        smiles, _, _ = self.chemistry._convert_graph_to_smiles(
            [list(c) for c in reading.coords], reading.symbols, reading.classes.tolist())
        return smiles


def load_set(bench: str, name: str, sample: int, seed: int):
    with open(os.path.join(bench, f'{name}.csv'), encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if sample and len(rows) > sample:
        rows = random.Random(seed).sample(rows, sample)
    root = os.path.dirname(os.path.abspath(bench.rstrip('/')))
    return [(row['image_id'], os.path.join(root, row['file_path']), row['SMILES']) for row in rows]


def run(args) -> None:
    from p2s import molfile
    from p2s.recognizer import OnnxRecognizer

    scorer = Scorer(args.molscribe_src)
    models = {}
    for spec in args.model:
        label, _, folder = spec.partition('=')
        models[label] = OnnxRecognizer(folder)
        models[label].white = args.white

    with open(args.results, 'a', encoding='utf-8') as out:
        for set_name in args.sets.split(','):
            pictures = load_set(args.bench, set_name, args.sample, args.seed)
            for variant in args.variants.split(','):
                for label, recognizer in models.items():
                    started = time.perf_counter()
                    for image_id, path, gold in pictures:
                        with open(path, 'rb') as f:
                            data = damaged(f.read(), variant)
                        t0 = time.perf_counter()
                        try:
                            reading = recognizer.read(data)
                        except Exception as error:      # a picture Pillow cannot open
                            print(f'{image_id}: {error}', file=sys.stderr)
                            continue
                        elapsed = time.perf_counter() - t0
                        structure = reading.structure
                        plugin = scorer.from_molfile(molfile.write(structure)) if not structure.empty else ''
                        upstream = scorer.upstream(reading)
                        gold_exact, gold_graph = scorer.canon(gold, False), scorer.canon(gold, True)
                        record = {
                            'set': set_name, 'variant': variant, 'model': label, 'white': args.white,
                            'id': image_id, 'gold': gold, 'plugin': plugin, 'upstream': upstream,
                            'stereo': '@' in gold_exact,
                            'exact': scorer.canon(plugin, False) == gold_exact,
                            'graph': scorer.canon(plugin, True) == gold_graph,
                            'upstream_exact': scorer.canon(upstream, False) == gold_exact,
                            'upstream_graph': scorer.canon(upstream, True) == gold_graph,
                            'confidence': round(structure.confidence, 4), 'atoms': len(structure.atoms),
                            'seconds': round(elapsed, 3),
                        }
                        out.write(json.dumps(record) + '\n')
                    out.flush()
                    print(f'{set_name:7} {variant:7} {label:5} {len(pictures)} pictures in '
                          f'{time.perf_counter() - started:.0f}s', flush=True)


def rescore(path: str, molscribe_src: str) -> None:
    """Scores stored results again (after a change to the scoring), without the model."""
    scorer = Scorer(molscribe_src)
    rows = [json.loads(line) for line in open(path, encoding='utf-8') if line.strip()]
    for row in rows:
        gold_exact, gold_graph = scorer.canon(row['gold'], False), scorer.canon(row['gold'], True)
        row['stereo'] = '@' in gold_exact
        for prefix, smiles in (('', row['plugin']), ('upstream_', row['upstream'])):
            row[prefix + 'exact'] = scorer.canon(smiles, False) == gold_exact
            row[prefix + 'graph'] = scorer.canon(smiles, True) == gold_graph
    with open(path, 'w', encoding='utf-8') as out:
        out.writelines(json.dumps(row) + '\n' for row in rows)


def summarise(path: str) -> None:
    rows = [json.loads(line) for line in open(path, encoding='utf-8') if line.strip()]
    groups = defaultdict(list)
    for row in rows:
        groups[(row['model'], row['white'], row['variant'], row['set'])].append(row)

    def pct(values):
        return f'{100 * sum(values) / len(values):5.1f}' if values else '    -'

    print(f"\n{'model':5} {'white':>5} {'variant':7} {'set':7} {'n':>4} {'exact':>6} {'graph':>6} "
          f"{'stereo':>6} {'up.ex':>6} {'up.st':>6} {'t med':>6}")
    for key in sorted(groups):
        group = groups[key]
        stereo = [r for r in group if r['stereo']]
        print(f'{key[0]:5} {key[1]:5} {key[2]:7} {key[3]:7} {len(group):4} {pct([r["exact"] for r in group]):>6} '
              f'{pct([r["graph"] for r in group]):>6} {pct([r["exact"] for r in stereo]):>6} '
              f'{pct([r["upstream_exact"] for r in group]):>6} {pct([r["upstream_exact"] for r in stereo]):>6} '
              f'{statistics.median(r["seconds"] for r in group):6.2f}')

    print('\nconfidence (all models and variants): share correct (graph) in each band, and how many')
    bands = [(0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.85), (0.85, 0.9), (0.9, 1.01)]
    for low, high in bands:
        band = [r for r in rows if low <= r['confidence'] < high]
        print(f'  {low:.2f}–{min(high, 1):.2f}: {pct([r["graph"] for r in band])}% of {len(band)}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--bench')
    parser.add_argument('--molscribe-src')
    parser.add_argument('--model', action='append', default=[], help='label=folder, repeatable')
    parser.add_argument('--sets', default=','.join(SETS))
    parser.add_argument('--sample', type=int, default=150, help='pictures per set (0: all)')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--variants', default='plain')
    parser.add_argument('--white', type=int, default=245)
    parser.add_argument('--results', required=True)
    parser.add_argument('--summarise', action='store_true', help='only print the summary of --results')
    parser.add_argument('--rescore', action='store_true', help='score --results again, then summarise')
    args = parser.parse_args()
    if args.rescore:
        rescore(args.results, args.molscribe_src)
    elif not args.summarise:
        if not (args.bench and args.molscribe_src and args.model):
            parser.error('--bench, --molscribe-src and --model are needed to run')
        run(args)
    summarise(args.results)
    return 0


if __name__ == '__main__':
    sys.exit(main())
