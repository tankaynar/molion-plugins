"""The table file: what is written is read back, and the shipped one is what it says."""

from nmr.table import Entry, ShiftTable


def test_round_trip(tmp_path):
    path = tmp_path / 'table.bin.gz'
    ShiftTable.write(str(path), {'source': 'test'}, {
        '13C': {5: Entry(128.5, 1.25, 12), 1: Entry(-3.2, 0.0, 1)},
        '1H': {9: Entry(7.26, 0.04, 300)},
    })
    table = ShiftTable.load(str(path))
    assert table.get('13C', 5) == Entry(128.5, 1.25, 12)
    assert table.get('13C', 1) == Entry(-3.2, 0.0, 1)
    assert table.get('13C', 9) is None
    assert table.get('1H', 9).count == 300
    assert table.header['source'] == 'test'


def test_the_shipped_table(table):
    assert table.header['source'] == 'nmrshiftdb2withsignals.sd'
    assert table.size('13C') > 100_000 and table.size('1H') > 50_000
