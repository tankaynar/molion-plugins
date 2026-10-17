"""Compound numbers in the order an SI lists them: 1, 2, 3a, 3b, 10 — or I, II, IV; or A, B.

Molion writes numbers in one style per document (arabic, roman or letters), each with an
optional series letter (3a). Sorting the text as text would put 10 before 2 and IV before V.
"""

from __future__ import annotations

import re

_ARABIC = re.compile(r'^(\d+)(.*)$')
_ALPHA = re.compile(r'^([A-Z]+)(.*)$')
_ROMAN = re.compile(r'^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')
_ROMAN_VALUES = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def _roman(text: str) -> int:
    total = 0
    for i, letter in enumerate(text):
        value = _ROMAN_VALUES[letter]
        following = _ROMAN_VALUES[text[i + 1]] if i + 1 < len(text) else 0
        total += -value if value < following else value
    return total


def _letters(text: str) -> int:
    value = 0
    for letter in text:
        value = value * 26 + ord(letter) - ord('A') + 1
    return value


def sort_key_for(numbers: list[str]):
    """A key for each of a document's numbers. Capitals read as roman numerals only when every
    capitalised number is one: "C" is 100 among I, II, but the third letter among A, B."""
    capitals = [m.group(1) for m in (_ALPHA.match(n) for n in numbers) if m]
    roman = bool(capitals) and all(_ROMAN.match(c) for c in capitals)

    def key(number: str):
        if match := _ARABIC.match(number):
            return (0, int(match.group(1)), match.group(2))
        if match := _ALPHA.match(number):
            head = match.group(1)
            return (1, _roman(head) if roman else _letters(head), match.group(2))
        return (2, 0, number)

    return key
