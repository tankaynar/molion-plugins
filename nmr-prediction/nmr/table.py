"""The shift table: for each HOSE code seen in nmrshiftdb2, the median of its measured
shifts, how widely they spread, and how many there were.

Stored as sorted 64-bit keys (nmr.hose.key) with their values in parallel arrays, gzipped:
small on disk, loaded in a fraction of a second, looked up by bisection. Nothing is ever
written, so the plugin runs in a read-only sandbox.

File layout (all little-endian), after gzip:
    b'MOLNMR\\x01\\n', uint32 header length, header JSON
    then for each nucleus in header["nuclei"]: count × uint64 keys (sorted),
    count × int16 median (1/100 ppm), count × uint16 spread (1/100 ppm),
    count × uint16 number of shifts
"""

from __future__ import annotations

import gzip
import json
import struct
import sys
from array import array
from bisect import bisect_left
from dataclasses import dataclass

MAGIC = b'MOLNMR\x01\n'
SCALE = 100.0


@dataclass(frozen=True)
class Entry:
    median: float
    spread: float
    count: int


class _Nucleus:
    def __init__(self, keys: array, medians: array, spreads: array, counts: array):
        self.keys, self.medians, self.spreads, self.counts = keys, medians, spreads, counts

    def get(self, key: int) -> Entry | None:
        i = bisect_left(self.keys, key)
        if i == len(self.keys) or self.keys[i] != key:
            return None
        return Entry(self.medians[i] / SCALE, self.spreads[i] / SCALE, self.counts[i])


class ShiftTable:
    def __init__(self, nuclei: dict[str, _Nucleus], header: dict):
        self._nuclei = nuclei
        self.header = header

    def get(self, nucleus: str, key: int) -> Entry | None:
        table = self._nuclei.get(nucleus)
        return table.get(key) if table else None

    def size(self, nucleus: str) -> int:
        table = self._nuclei.get(nucleus)
        return len(table.keys) if table else 0

    @staticmethod
    def load(path: str) -> 'ShiftTable':
        with gzip.open(path, 'rb') as f:
            data = f.read()
        if not data.startswith(MAGIC):
            raise ValueError(f'{path} is not a shift table')
        offset = len(MAGIC)
        (length,) = struct.unpack_from('<I', data, offset)
        offset += 4
        header = json.loads(data[offset:offset + length].decode('utf-8'))
        offset += length

        nuclei = {}
        for nucleus in header['nuclei']:
            count = header['counts'][nucleus]
            parts = []
            for code, width in (('Q', 8), ('h', 2), ('H', 2), ('H', 2)):
                part = array(code)
                part.frombytes(data[offset:offset + count * width])
                if sys.byteorder == 'big':
                    part.byteswap()
                parts.append(part)
                offset += count * width
            nuclei[nucleus] = _Nucleus(*parts)
        return ShiftTable(nuclei, header)

    @staticmethod
    def write(path: str, header: dict, entries: dict[str, dict[int, Entry]]) -> None:
        """Writes `entries` (nucleus → key → Entry), keys sorted, with `header`."""
        header = dict(header, nuclei=list(entries), counts={n: len(e) for n, e in entries.items()})
        blob = bytearray(MAGIC)
        encoded = json.dumps(header, sort_keys=True).encode('utf-8')
        blob += struct.pack('<I', len(encoded)) + encoded
        for nucleus, table in entries.items():
            keys = sorted(table)
            columns = (
                array('Q', keys),
                array('h', [max(-32768, min(32767, round(table[k].median * SCALE))) for k in keys]),
                array('H', [max(0, min(65535, round(table[k].spread * SCALE))) for k in keys]),
                array('H', [max(0, min(65535, table[k].count)) for k in keys]),
            )
            for column in columns:
                if sys.byteorder == 'big':
                    column.byteswap()
                blob += column.tobytes()
        # mtime=0: the same table always gives the same bytes, so git sees no change.
        with open(path, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=9, mtime=0) as f:
            f.write(bytes(blob))
