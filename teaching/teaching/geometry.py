"""Where things are in a get-scene answer: boxes, centres and reading order. Pure."""

from __future__ import annotations

BOND = 50.8                 # Molion's bond length, canvas units


def molecule(scene: dict, molecule_id: str) -> dict | None:
    return next((m for m in scene.get('molecules') or [] if m['id'] == molecule_id), None)


def molecule_of_atom(scene: dict, atom_id: str) -> dict | None:
    return next((m for m in scene.get('molecules') or [] if any(a['id'] == atom_id for a in m['atoms'])), None)


def molecule_of_bond(scene: dict, bond_id: str) -> dict | None:
    return next((m for m in scene.get('molecules') or [] if any(b['id'] == bond_id for b in m['bonds'])), None)


def box(points) -> tuple[float, float, float, float]:
    """(min x, min y, max x, max y) of (x, y) points."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def molecule_box(mol: dict) -> tuple[float, float, float, float]:
    return box([(a['x'], a['y']) for a in mol['atoms']])


def centre(b: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def right_of(b: tuple[float, float, float, float], gap: float = 1.5 * BOND) -> float:
    """An x clear of a box on its right."""
    return b[2] + gap


def rows(items: list[tuple[str, float, float]], gap: float = 2.5 * BOND) -> dict[str, int]:
    """Each item's row, top to bottom: items whose centres are closer than `gap` in y share
    a row. `items` are (key, x, y)."""
    ordered = sorted(items, key=lambda item: item[2])
    result, row, last = {}, 0, None
    for key, _, y in ordered:
        if last is not None and y - last > gap:
            row += 1
        result[key] = row
        last = y
    return result


def reading_order(items: list[tuple[str, float, float]]) -> list[str]:
    """Keys in reading order: rows top to bottom, each left to right."""
    row = rows(items)
    return [key for key, x, y in sorted(items, key=lambda item: (row[item[0]], item[1], item[2]))]
