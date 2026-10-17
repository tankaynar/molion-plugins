#!/usr/bin/env python3
"""Builds data/shifts.bin.gz from nmrshiftdb2's assigned spectra.

    python tools/build_table.py --sd nmrshiftdb2withsignals.sd [--out data/shifts.bin.gz]
                                [--holdout 20]

Needs RDKit 2025.9.2, the version Molion perceives structures with.

nmrshiftdb2withsignals.sd is downloaded from https://sourceforge.net/projects/nmrshiftdb2/
(files/data). Its data is under the nmrshiftdb2 Database License, and so is the table this
builds (see NOTICE).

Only measured spectra are used. A record lists, per spectrum index, the program that
predicted or calculated it (fields Program, NMRProgram, NMRMethod): those are skipped, or
the table would learn from other predictors.

With --holdout N, every Nth record (by nmrshiftdb2 ID) is kept out of the table and the
table is then tested on them: the mean absolute error per nucleus is printed. Build the
table you ship without it.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import re
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from nmr import hose, predict                     # noqa: E402
from nmr.structure import read                    # noqa: E402
from nmr.table import Entry, ShiftTable          # noqa: E402

NUCLEI = {'13C': predict.CARBON, '1H': predict.PROTON}
SPECTRUM = re.compile(r'^Spectrum (13C|1H) (\d+)$')
INDEXED = re.compile(r'(\d+):(.*?)(?=\s+\d+:|\s*$)')

# Shifts outside these are typos, not chemistry.
PLAUSIBLE = {predict.CARBON: (-20.0, 260.0), predict.PROTON: (-5.0, 20.0)}


def split_records(path):
    record = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            record.append(line)
            if line.startswith('$$$$'):
                yield ''.join(record)
                record = []


def indexed(value: str) -> dict[int, str]:
    """'0:298 1:300' → {0: '298', 1: '300'}: the per-spectrum values of a record's fields."""
    return {int(i): v.strip() for i, v in INDEXED.findall(value or '')}


def samples_of(text: str):
    """(nmrshiftdb2 id, [(nucleus, depth, key, shift)], structure) for one SD record, or None."""
    from rdkit import Chem, RDLogger
    from structure_json import describe
    RDLogger.DisableLog('rdApp.*')

    mol = Chem.MolFromMolBlock(text.split('M  END')[0] + 'M  END', sanitize=True, removeHs=False)
    if mol is None:
        return None
    props = {}
    for name, value in re.findall(r'^> <(.+?)>\n(.*?)\n\n', text.split('M  END', 1)[1], re.S | re.M):
        props[name] = value.strip()
    record_id = int(props.get('nmrshiftdb2 ID', '0') or 0)

    # Spectra a program predicted or calculated.
    excluded = set()
    for field in ('Program', 'NMRProgram', 'NMRMethod'):
        excluded |= set(indexed(props.get(field, '')))

    structure = read(describe(mol))
    codes_cache = {}
    samples = []
    for name, value in props.items():
        match = SPECTRUM.match(name)
        if not match or int(match.group(2)) in excluded:
            continue
        nucleus = NUCLEI[match.group(1)]
        low, high = PLAUSIBLE[nucleus]
        per_atom = defaultdict(list)
        for signal in value.split('|'):
            parts = signal.split(';')
            if len(parts) < 3:
                continue
            try:
                shift, index = float(parts[0]), int(parts[2])
            except ValueError:
                continue
            if not (0 <= index < mol.GetNumAtoms()) or not (low <= shift <= high):
                continue
            atom = structure.atoms[index]
            if atom.is_hydrogen:
                # A drawn H: its shift belongs to the heavy atom it is on.
                heavy = [n.GetIdx() for n in mol.GetAtomWithIdx(index).GetNeighbors() if n.GetAtomicNum() > 1]
                if not heavy:
                    continue
                atom = structure.atoms[heavy[0]]
            if nucleus == predict.CARBON and atom.element != 'C':
                continue
            if nucleus == predict.PROTON and atom.hydrogens == 0:
                continue
            per_atom[atom.index].append(shift)
        for index, shifts in per_atom.items():
            if index not in codes_cache:
                codes_cache[index] = hose.codes(structure, index)
            shift = sum(shifts) / len(shifts)
            for depth, code in enumerate(codes_cache[index], start=1):
                samples.append((nucleus, depth, hose.key(nucleus, depth, code), shift))
    return record_id, samples


# Values closer to the median than this are never dropped as outliers, however tightly the
# rest agree: a ppm for carbon, a twentieth for hydrogen.
OUTLIER_FLOOR = {predict.CARBON: 1.0, predict.PROTON: 0.05}


def robust(values: list[float], floor: float) -> Entry:
    """Median and spread of one code's shifts, after dropping what lies far off the rest."""
    median = statistics.median(values)
    if len(values) >= 3:
        mad = statistics.median(abs(v - median) for v in values) * 1.4826
        limit = max(3 * mad, floor)
        kept = [v for v in values if abs(v - median) <= limit]
        if kept:
            values = kept
            median = statistics.median(values)
    spread = statistics.median(abs(v - median) for v in values) * 1.4826 if len(values) >= 3 else (
        abs(values[0] - values[1]) / 2 if len(values) == 2 else 0.0)
    return Entry(median, spread, len(values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sd', required=True)
    parser.add_argument('--out', default=os.path.join(ROOT, 'data', 'shifts.bin.gz'))
    parser.add_argument('--holdout', type=int, default=0)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    args = parser.parse_args()

    with open(args.sd, 'rb') as f:
        checksum = hashlib.sha256(f.read()).hexdigest()

    collected = {n: defaultdict(list) for n in NUCLEI.values()}
    held_out = []
    records = spectra_used = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(samples_of, split_records(args.sd), chunksize=64):
            if result is None:
                continue
            record_id, samples = result
            records += 1
            if args.holdout and record_id % args.holdout == 0:
                held_out.append(samples)
                continue
            for nucleus, _, key, shift in samples:
                collected[nucleus][key].append(shift)
            spectra_used += 1 if samples else 0
            if records % 5000 == 0:
                print(f'  {records} records', file=sys.stderr)

    tables = {n: {k: robust(v, OUTLIER_FLOOR[n]) for k, v in codes.items()} for n, codes in collected.items()}
    header = {
        'source': 'nmrshiftdb2withsignals.sd',
        'sha256': checksum,
        'built': datetime.date.today().isoformat(),
        'maxDepth': hose.MAX_DEPTH,
        'records': records,
        'holdout': args.holdout,
    }
    ShiftTable.write(args.out, header, tables)
    print(f'{records} records; codes: ' + ', '.join(f'{n} {len(t)}' for n, t in tables.items()))
    print(f'wrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB), sha256 of source {checksum}')

    if held_out:
        evaluate(ShiftTable.load(args.out), held_out)
    return 0


def evaluate(table: ShiftTable, held_out) -> None:
    """Mean absolute error of the deepest match for each held-out atom, per nucleus."""
    for nucleus in NUCLEI.values():
        errors, by_depth, missing = [], defaultdict(list), 0
        for samples in held_out:
            # The record's samples come per atom, MAX_DEPTH in a row, depth 1 first.
            group = [s for s in samples if s[0] == nucleus]
            for start in range(0, len(group), hose.MAX_DEPTH):
                entries = group[start:start + hose.MAX_DEPTH]
                shift = entries[0][3]
                found = None
                for _, depth, key, _ in reversed(entries):
                    entry = table.get(nucleus, key)
                    if entry is not None:
                        found = (depth, entry.median)
                        break
                if found is None:
                    missing += 1
                    continue
                errors.append(abs(found[1] - shift))
                by_depth[found[0]].append(abs(found[1] - shift))
        if not errors:
            continue
        print(f'{nucleus}: MAE {statistics.mean(errors):.3f} ppm over {len(errors)} atoms, '
              f'{missing} without any match')
        for depth in sorted(by_depth):
            values = by_depth[depth]
            print(f'    depth {depth}: MAE {statistics.mean(values):.3f} ({len(values)} atoms)')


if __name__ == '__main__':
    sys.exit(main())
