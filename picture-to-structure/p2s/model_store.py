"""The recognition model on this computer: downloaded once into the plugin's data folder.

Files go into `model-<version>.part/` as they arrive, each checked against its SHA-256, and the
folder is renamed to `model-<version>/` only when every file has passed. A download cut short
therefore never looks finished, and the next attempt starts again cleanly. A `verified` file
inside marks a finished folder, so the model is not hashed again on every launch.

MOLION_P2S_MODEL_DIR points at a model folder elsewhere (one exported locally with
tools/export_onnx.py), for development before a release carries the files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass
from typing import Callable

MODEL_DIR_ENV = 'MOLION_P2S_MODEL_DIR'
VERSION = 'v1'
SOURCE = 'github.com/tankaynar/molion-plugins'
_RELEASE = 'https://github.com/tankaynar/molion-plugins/releases/download/p2s-model-v1/'


@dataclass(frozen=True)
class ModelFile:
    name: str
    url: str
    size: int
    sha256: str


# The int8 export (tools/export_onnx.py --int8), uploaded to the release above. manifest.json
# lists the others' hashes but cannot hold its own, so it is pinned here too.
FILES: tuple[ModelFile, ...] = (
    ModelFile('encoder.onnx', _RELEASE + 'encoder.onnx', 123324158,
              '954d316a5f59312854b1f7fd1f20ab14d22fe93b9fcc99b3d1334a72531328a2'),
    ModelFile('decoder.onnx', _RELEASE + 'decoder.onnx', 11936912,
              '00a5a9d401c4fadc878fe6b59f67b3ca738cab96eac1b1bc5d39f5ef43e9e309'),
    ModelFile('edges.onnx', _RELEASE + 'edges.onnx', 544040,
              '8dff3b7d850c45b16e11aa276d5f071d59194d82bc3ae9674904c89f96b5b1fb'),
    ModelFile('vocab.json', _RELEASE + 'vocab.json', 930,
              '72ae8c9191a6e5b88726ab4a2fffee05c9facbce18d1efa215829a9857b2eafa'),
    ModelFile('manifest.json', _RELEASE + 'manifest.json', 1467,
              'b53733e6bbcd952baefc776a384e00d9ef04c65fea0a1eab0aa0cad25e804af6'),
)

CHUNK = 1 << 20


class ModelError(RuntimeError):
    """The model could not be fetched or did not match what was expected."""


def _fetch(url: str, timeout: float):
    return urllib.request.urlopen(url, timeout=timeout)


class ModelStore:
    def __init__(self, data_dir: str | None, files: tuple[ModelFile, ...] = FILES,
                 version: str = VERSION, fetch: Callable = _fetch) -> None:
        self.data_dir = data_dir
        self.files = files
        self.version = version
        self._fetch = fetch

    @property
    def override(self) -> str | None:
        return os.environ.get(MODEL_DIR_ENV) or None

    @property
    def folder(self) -> str | None:
        if self.override:
            return self.override
        if not self.data_dir:
            return None
        return os.path.join(self.data_dir, f'model-{self.version}')

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def published(self) -> bool:
        return bool(self.files)

    def ready(self) -> bool:
        folder = self.folder
        if folder is None:
            return False
        if self.override:
            return os.path.isdir(folder)
        return os.path.isfile(os.path.join(folder, 'verified'))

    def download(self, progress: Callable[[str, float | None], None]) -> str:
        """Fetches every file, checks it, and returns the finished folder."""
        if self.ready():
            return self.folder
        if not self.data_dir:
            raise ModelError('Molion gave Picture to Structure no folder to keep its model in.')
        if not self.published:
            raise ModelError('The recognition model is not published yet.')

        final = self.folder
        partial = final + '.part'
        shutil.rmtree(partial, ignore_errors=True)
        os.makedirs(partial)

        total, received = self.total_size or 1, 0
        for model_file in self.files:
            digest = hashlib.sha256()
            path = os.path.join(partial, model_file.name)
            try:
                with self._fetch(model_file.url, 60) as response, open(path, 'wb') as out:
                    while True:
                        chunk = response.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
                        progress('Downloading recognition model', min(received / total, 1.0))
            except OSError as error:
                shutil.rmtree(partial, ignore_errors=True)
                raise ModelError(f'Could not download the recognition model: {error}') from error
            if digest.hexdigest() != model_file.sha256:
                shutil.rmtree(partial, ignore_errors=True)
                raise ModelError(f'The downloaded {model_file.name} was damaged. Try again.')

        with open(os.path.join(partial, 'verified'), 'w', encoding='utf-8') as marker:
            json.dump({'version': self.version, 'files': [f.name for f in self.files]}, marker)
            marker.write('\n')
        shutil.rmtree(final, ignore_errors=True)
        os.replace(partial, final)
        return final


def size_text(size: int) -> str:
    return f'{size / 1_000_000:.0f} MB' if size >= 1_000_000 else f'{max(size, 1) / 1000:.0f} KB'
