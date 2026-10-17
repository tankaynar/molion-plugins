"""What the plugin remembers between runs: the adduct last chosen. Kept in its data folder."""

from __future__ import annotations

import json
import os

from si import hrms
from si.rpc import log


class Settings:
    def __init__(self, data_dir: str | None = None) -> None:
        self._path = os.path.join(data_dir, 'settings.json') if data_dir else None
        self.adduct_id = hrms.DEFAULT
        if self._path and os.path.exists(self._path):
            try:
                with open(self._path, encoding='utf-8') as file:
                    stored = json.load(file).get('adduct')
                if stored in hrms.BY_ID:
                    self.adduct_id = stored
            except (OSError, ValueError, AttributeError) as error:
                log(f'settings ignored: {error}')

    @property
    def adduct(self) -> hrms.Adduct:
        return hrms.BY_ID[self.adduct_id]

    def remember(self, adduct_id: str) -> None:
        self.adduct_id = adduct_id
        if not self._path:
            return
        try:
            with open(self._path, 'w', encoding='utf-8', newline='\n') as file:
                json.dump({'adduct': adduct_id}, file)
        except OSError as error:
            log(f'settings not saved: {error}')
