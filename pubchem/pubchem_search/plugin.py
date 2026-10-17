"""The plugin's answers to Molion: `query` (a search, as palette rows) and `invoke` (a row
chosen: PubChem's drawing of it, for Molion to place).

Answers are kept for a few minutes, so typing back to an earlier query, or the same search in
a moment, asks PubChem nothing; PubChem asks for no more than five requests a second.
"""

from __future__ import annotations

import socket
import time
import urllib.error

from . import search as pubchem

CACHE_SECONDS = 300
CACHE_SIZE = 100

UNREACHABLE = 'PubChem could not be reached.'
BUSY = 'PubChem is busy. Try again in a moment.'


def _failure_message(error):
    if isinstance(error, urllib.error.HTTPError) and error.code in (429, 503):
        return BUSY
    if isinstance(error, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError)):
        return UNREACHABLE
    return 'The search failed.'


class PubChemPlugin:
    def __init__(self, fetch, clock=time.monotonic):
        self._fetch = fetch
        self._clock = clock
        self._answers = {}      # query (lower case) → (time, rows)
        self._hits = {}         # cid → the search result it came from, for invoke's fallback

    # ── query ─────────────────────────────────────────────────────────────

    def query(self, params):
        text = (params.get('text') or '').strip()
        if len(text) < 2:
            return {'results': []}
        key = text.lower()
        cached = self._answers.get(key)
        if cached and self._clock() - cached[0] < CACHE_SECONDS:
            return {'results': cached[1]}

        try:
            hits = pubchem.search(text, self._fetch)
        except Exception as error:
            return {'results': [], 'message': _failure_message(error)}

        rows = [self._row(hit) for hit in hits]
        for hit in hits:
            self._hits[hit['cid']] = hit
        self._remember(key, rows)
        return {'results': rows}

    @staticmethod
    def _row(hit):
        # The IUPAC name when it says something the title does not; otherwise the synonym
        # typed, when that is how it was found ("heme" for Hemin).
        iupac = hit.get('iupac') or ''
        matched = hit.get('matched')
        if iupac and iupac.lower() != hit['name'].lower():
            subtitle = iupac
        elif matched and matched.lower() != hit['name'].lower():
            subtitle = f'Also called {matched}'
        else:
            subtitle = None
        details = [part for part in (hit.get('formula'), f"MW {hit['mw']:.1f}" if hit.get('mw') else None,
                                     f"CID {hit['cid']}") if part]
        row = {'id': str(hit['cid']), 'title': hit['name'][:200], 'detail': '  •  '.join(details)}
        if subtitle:
            row['subtitle'] = subtitle[:200]
        smiles = hit.get('smiles') or ''
        if smiles and len(smiles) <= 2000:
            row['smiles'] = smiles
        return row

    def _remember(self, key, rows):
        now = self._clock()
        if len(self._answers) >= CACHE_SIZE:
            for stale in [k for k, (t, _) in self._answers.items() if now - t >= CACHE_SECONDS]:
                del self._answers[stale]
            if len(self._answers) >= CACHE_SIZE:
                del self._answers[min(self._answers, key=lambda k: self._answers[k][0])]
        self._answers[key] = (now, rows)

    # ── invoke ────────────────────────────────────────────────────────────

    def invoke(self, params):
        result = params.get('result') or {}
        cid_text = str(result.get('id') or '')
        if not cid_text.isdigit():
            return {'ok': False, 'error': 'Choose a compound from Search PubChem.'}
        cid = int(cid_text)
        hit = self._hits.get(cid, {})
        title = hit.get('name')

        try:
            molfile = pubchem.record_2d(cid, self._fetch)
            return {'ok': True, 'place': {'molfile': molfile, 'title': title, 'hydrogens': 'fold'}}
        except pubchem.NotFound:
            pass
        except Exception as error:
            if not hit.get('smiles'):
                return {'ok': False, 'error': _failure_message(error)}
        # No drawing to be had: Molion lays out the SMILES the search found.
        if hit.get('smiles'):
            return {'ok': True, 'place': {'smiles': hit['smiles'], 'title': title}}
        return {'ok': False, 'error': f'PubChem has no structure for CID {cid}.'}
