"""The plugin's commands, and the adduct search of Copy HRMS Line…."""

from __future__ import annotations

from si import compounds as scope
from si import elemental, hrms, stub
from si.settings import Settings

NOTHING_DRAWN = 'Draw a structure first.'


def _plural(n: int, word: str) -> str:
    return f'{n} {word}' + ('' if n == 1 else 's')


def _plain(text: str) -> str:
    """"[M+NH₄]⁺" as typed: "[m+nh4]+"."""
    return text.translate(str.maketrans('⁺⁻−₄·', '+--4 ')).strip().lower()


def _matches(adduct: hrms.Adduct, text: str) -> bool:
    """"na" finds [M+Na]⁺ and "m-h" [M−H]⁻; "neg" and "esi" find what they name. Words match
    from their start, so "na" is not the end of "protonated"."""
    label = _plain(adduct.label).strip('[]+- ')
    if any(sign in text for sign in '+-'):
        return text.strip('[]') in _plain(adduct.label)
    words = [label, *label.replace('-', '+').split('+'), adduct.ionisation.lower(), *adduct.keywords.split()]
    return any(word.startswith(text) for word in words)


def _unnamed(compounds) -> str:
    reason = scope.why_unnamed(compounds)
    return f', without names ({reason.rstrip(".")})' if reason else ''


class Actions:
    def __init__(self, host, settings: Settings | None = None) -> None:
        self.host = host
        self.settings = settings or Settings()

    # ── Copy HRMS Line… ──────────────────────────────────────────────────

    def query(self, params: dict) -> dict:
        if params.get('contributionId') != 'copy-hrms':
            return {'results': []}
        text = _plain(params.get('text') or '').replace(' ', '')
        adducts = [a for a in hrms.ADDUCTS if not text or _matches(a, text)]
        # The one chosen last comes first: most of a project's compounds are run the same way.
        adducts.sort(key=lambda a: a.id != self.settings.adduct_id)
        if not adducts:
            return {'results': [], 'message': 'No adduct matches.'}

        compounds = [c for c in scope.selected(self.host) if c.structure]
        if not compounds:
            return {'results': [], 'message': NOTHING_DRAWN}
        return {'results': [self._row(adduct, compounds) for adduct in adducts]}

    def _row(self, adduct: hrms.Adduct, compounds) -> dict:
        row = {'id': adduct.id, 'title': adduct.label, 'section': adduct.ionisation}
        if len(compounds) > 1:
            row['subtitle'] = f'One line for each of {len(compounds)} structures'
            return row
        try:
            ion = hrms.ion(compounds[0].structure, adduct)
            row['subtitle'] = f'm/z {ion.mz:.4f} · {ion.formula}'
            if ion.label != adduct.label:
                row['detail'] = f'Drawn as an ion, so measured as {ion.label}'
        except hrms.NotMeasurable as reason:
            row['subtitle'] = f'No m/z: {reason}'
        return row

    def copy_hrms(self, adduct_id: str | None) -> dict:
        adduct = hrms.BY_ID.get(adduct_id or '') or self.settings.adduct
        self.settings.remember(adduct.id)
        lines, skipped = [], []
        for compound in scope.selected(self.host):
            try:
                lines.append(hrms.ion(compound.structure or {}, adduct).line())
            except hrms.NotMeasurable as reason:
                skipped.append(str(reason))
        return self._copy(lines, skipped, 'HRMS line')

    # ── Copy Elemental Analysis ──────────────────────────────────────────

    def copy_elemental(self) -> dict:
        lines, skipped = [], []
        for compound in scope.selected(self.host):
            try:
                lines.append(elemental.line(compound.structure or {}))
            except elemental.NotAnalysable as reason:
                skipped.append(str(reason))
        return self._copy(lines, skipped, 'elemental analysis')

    def _copy(self, lines: list[str], skipped: list[str], what: str) -> dict:
        if not lines:
            return {'ok': False, 'error': f'No {what}: {skipped[0]}.' if skipped else NOTHING_DRAWN}
        self.host.copy('\n'.join(lines))
        message = f'Copied {_plural(len(lines), what)}' if len(lines) > 1 else f'Copied {what}'
        if skipped:
            message += f' ({_plural(len(skipped), "structure")} left out: {skipped[0]})'
        return {'ok': True, 'message': message}

    # ── The SI stub ──────────────────────────────────────────────────────

    def _stub_compounds(self):
        compounds = scope.everything(self.host)
        return scope.with_strings(self.host, compounds) if compounds else compounds

    def copy_stub(self) -> dict:
        compounds = self._stub_compounds()
        if not compounds:
            return {'ok': False, 'error': NOTHING_DRAWN}
        self.host.copy(stub.text(compounds, self.settings.adduct))
        return {'ok': True, 'message': f'Copied the SI stub for {_plural(len(compounds), "compound")}'
                                       + _unnamed(compounds)}

    def export_stub(self) -> dict:
        compounds = self._stub_compounds()
        if not compounds:
            return {'ok': False, 'error': NOTHING_DRAWN}
        saved = self.host.save_file(stub.csv_text(compounds, self.settings.adduct), title='Export SI Stub',
                                    suggested_name='si-stub.csv', extension='csv')
        if saved.get('cancelled'):
            return {'ok': True}
        return {'ok': True, 'message': f'Saved {saved.get("name") or "the SI stub"}' + _unnamed(compounds)}

    def invoke(self, params: dict) -> dict:
        contribution = params.get('contributionId')
        if contribution == 'copy-hrms':
            return self.copy_hrms((params.get('result') or {}).get('id'))
        if contribution == 'copy-elemental':
            return self.copy_elemental()
        if contribution == 'copy-stub':
            return self.copy_stub()
        if contribution == 'export-stub':
            return self.export_stub()
        return {'ok': False, 'error': f'unknown contribution {contribution!r}'}
