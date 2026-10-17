"""PubChem search and records (PUG REST), with the fetch injected so tests use recorded answers.

Search: PubChem's autocomplete ranks by popularity, not by match, so an exact name can sit far
down its list ("heme" is tenth, after Hemellitic acid and Hemel). An exact name lookup runs
beside it and comes first. Every hit is then described by one batch property request.

Records: PubChem's own 2D drawing of a compound, not a layout of its SMILES. A SMILES cannot
say where a disconnected ion sits, so heme's iron landed beside the porphyrin instead of in it.
The record lists every hydrogen and is drawn at PubChem's scale; Molion folds and scales it.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://pubchem.ncbi.nlm.nih.gov/rest'

# PubChem asks for no more than five requests a second.
MAX_PARALLEL = 4
EXACT_HITS = 4
SUGGESTIONS = 10
RESOLVED_SUGGESTIONS = 5
LIMIT = 8

PROPERTIES = 'Title,MolecularFormula,MolecularWeight,SMILES,ConnectivitySMILES,IUPACName,InChI'

INCHIKEY = re.compile(r'^[A-Z]{14}-[A-Z]{10}-[A-Z]$')


class NotFound(Exception):
    pass


def _log(message):
    print(f'[pubchem] {message}', file=sys.stderr, flush=True)


def _quote(text):
    return urllib.parse.quote(text, safe='')


def _json(fetch, url, timeout):
    return json.loads(fetch(url, timeout))


def _cids(fetch, url, timeout=4):
    """The CIDs a lookup answers, or none: PubChem answers 404 for a name it does not know."""
    try:
        return _json(fetch, url, timeout).get('IdentifierList', {}).get('CID', [])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def _suggestions(fetch, query):
    url = f'{BASE}/autocomplete/compound/{_quote(query)}/json?limit={SUGGESTIONS}'
    return _json(fetch, url, 4).get('dictionary_terms', {}).get('compound', [])


def _first_cid(fetch, name):
    try:
        cids = _cids(fetch, f'{BASE}/pug/compound/name/{_quote(name)}/cids/JSON', timeout=3)
    except Exception:
        return None  # one suggestion failing costs that suggestion, not the search
    return cids[0] if cids else None


def display_name(name):
    """"TETRAHYDROFURAN" → "Tetrahydrofuran"; otherwise the first letter capitalised."""
    if not name:
        return name
    if name == name.upper() and len(name) > 3:
        return name.title()
    return name[0].upper() + name[1:]


def _smiles(props):
    for key in ('SMILES', 'ConnectivitySMILES', 'IsomericSMILES', 'CanonicalSMILES'):
        if props.get(key):
            return props[key]
    return ''


def search(query, fetch, limit=LIMIT):
    """Compounds for what the user typed: a name, a CID or an InChIKey. Each is
    {cid, name, iupac, formula, smiles, inchi, mw, matched?}: `matched` is the synonym the
    query named exactly ("heme" for Hemin), when the exact lookup found it."""
    q = query.strip()
    if len(q) < 2:
        return []

    # (cid, name shown, the synonym that matched exactly) in result order.
    if q.isdigit():
        hits = [(int(q), None, None)]
    elif INCHIKEY.match(q):
        hits = [(cid, None, None) for cid in _cids(fetch, f'{BASE}/pug/compound/inchikey/{q}/cids/JSON')]
    else:
        with ThreadPoolExecutor(MAX_PARALLEL) as pool:
            exact = pool.submit(_cids, fetch, f'{BASE}/pug/compound/name/{_quote(q)}/cids/JSON')
            suggested = pool.submit(_suggestions, fetch, q)
            try:
                names = [n for n in suggested.result() if n.strip().lower() != q.lower()]
            except Exception as e:
                _log(f'autocomplete failed: {e}')
                names = []
            names = names[:RESOLVED_SUGGESTIONS]
            resolved = list(pool.map(lambda name: _first_cid(fetch, name), names))
            # The exact lookup failing for want of a network fails the search: an empty list
            # would read as "PubChem has nothing".
            exact_cids = exact.result()[:EXACT_HITS]
        hits = [(cid, None, q) for cid in exact_cids]
        hits += [(cid, name, None) for cid, name in zip(resolved, names) if cid]

    seen = set()
    unique = []
    for cid, name, matched in hits:
        if cid not in seen:
            seen.add(cid)
            unique.append((cid, name, matched))
    unique = unique[:limit]
    if not unique:
        return []

    try:
        url = f'{BASE}/pug/compound/cid/{",".join(str(c) for c, _, _ in unique)}/property/{PROPERTIES}/JSON'
        table = _json(fetch, url, 5).get('PropertyTable', {}).get('Properties', [])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    by_cid = {p.get('CID'): p for p in table}

    results = []
    for cid, name, matched in unique:
        p = by_cid.get(cid)
        if p is None:
            continue
        result = {
            'cid': cid,
            'name': display_name(name or p.get('Title') or p.get('IUPACName') or f'CID {cid}'),
            'iupac': p.get('IUPACName', ''),
            'formula': p.get('MolecularFormula', ''),
            'smiles': _smiles(p),
            'inchi': p.get('InChI', ''),
            'mw': float(p.get('MolecularWeight', 0) or 0),
        }
        if matched:
            result['matched'] = matched
        results.append(result)
    return results


def record_2d(cid, fetch):
    """PubChem's 2D drawing of a compound: the first record of its SDF, up to M  END (the
    data fields after it are not a drawing). Raises NotFound for a CID PubChem has no
    drawing of."""
    try:
        sdf = fetch(f'{BASE}/pug/compound/cid/{int(cid)}/SDF?record_type=2d', 8).decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(f'PubChem has no drawing of CID {cid}')
        raise
    record = sdf.replace('\r\n', '\n').split('$$$$')[0]
    end = record.find('M  END')
    if end < 0:
        raise ValueError('PubChem sent a record without a structure')
    return record[:end + len('M  END')] + '\n'
