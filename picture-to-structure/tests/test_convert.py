import base64

import pytest

import main
from conftest import FakeMolion, picture
from p2s.model_store import MODEL_DIR_ENV, ModelFile, ModelStore
from p2s.rpc import Host
from p2s.structure import Atom, Bond, Structure

ETHANOL = Structure([Atom('C', 0, 0), Atom('C', 40, 0), Atom('O', 60, 35)], [Bond(0, 1), Bond(1, 2)])


class FakeRecognizer:
    def __init__(self, structure=ETHANOL):
        self.structure = structure
        self.seen = []

    def recognise(self, data, crop):
        self.seen.append((data, crop))
        return self.structure


class FakeStore(ModelStore):
    """Ready, or not yet downloaded and then 'downloaded' instantly."""

    def __init__(self, ready=True):
        super().__init__('/data', (ModelFile('m.onnx', 'http://x/m.onnx', 310_000_000, '0' * 64),))
        self._ready = ready
        self.downloads = 0

    def ready(self):
        return self._ready

    @property
    def folder(self):
        return '/data/model-v1'

    def download(self, progress):
        self.downloads += 1
        progress('Downloading recognition model', 1.0)
        self._ready = True
        return self.folder


@pytest.fixture(autouse=True)
def no_override(monkeypatch):
    monkeypatch.delenv(MODEL_DIR_ENV, raising=False)


def run(molion, store=None, recognizer=None, images=('img-1',)):
    recognizer = recognizer or FakeRecognizer()
    queue = [
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"dataDir":"/data"}}',
        '{"jsonrpc":"2.0","id":5,"method":"invoke","params":{"contributionId":"convert","kind":"action",'
        '"context":{"images":%s}}}' % str(list(images)).replace("'", '"'),
    ]

    def readline():
        if molion.pending():
            return molion.readline()
        return queue.pop(0) + '\n' if queue else ''

    host = Host(readline, molion.write)
    original = main.Converter

    class WithStore(original):
        def __init__(self, host, _store, load):
            super().__init__(host, store or FakeStore(), load)

    main.Converter = WithStore
    try:
        main.serve(host, load=lambda folder: recognizer)
    finally:
        main.Converter = original
    return [r for r in molion.replies if r.get('id') == 5][-1], recognizer


def test_initialize_names_the_plugin():
    molion = FakeMolion()
    lines = ['{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}']
    main.serve(Host(lambda: lines.pop(0) + '\n' if lines else '', molion.write))
    assert molion.replies[0]['result']['name'] == 'Picture to Structure'


def test_the_picture_is_replaced_by_the_molecule_where_it_was():
    molion = FakeMolion({'scene:get-image': picture(data=base64.b64encode(b'png').decode(),
                                                    crop={'left': 0.1, 'top': 0, 'right': 1, 'bottom': 1})})
    reply, recognizer = run(molion)
    assert reply['result'] == {'ok': True, 'message': 'Converted to a structure.'}
    assert recognizer.seen == [(b'png', {'left': 0.1, 'top': 0, 'right': 1, 'bottom': 1})]
    assert molion.calls('scene:delete') == [{'operation': 'delete', 'payload': {'images': ['img-1']}}]
    [added] = molion.calls('scene:add-from-molfile')
    assert (added['payload']['x'], added['payload']['y']) == (100.0, 50.0)
    assert added['payload']['molfile'].endswith('M  END\n')
    operations = [m['params']['operation'] for m in molion.sent if m.get('method') == 'scene']
    assert operations == ['get-image', 'delete', 'add-from-molfile']


def test_a_locked_picture_stays_and_the_molecule_goes_beside_it():
    molion = FakeMolion({'scene:get-image': picture(), 'scene:delete': Exception('locked by molion.tlc')})
    reply, _ = run(molion)
    assert reply['result']['ok'] is True
    assert 'locked' in reply['result']['message']
    [added] = molion.calls('scene:add-from-molfile')
    assert added['payload']['x'] == 300.0


def test_a_drawing_is_not_a_bitmap():
    molion = FakeMolion({'scene:get-image': picture(data=None, kind='vector')})
    reply, recognizer = run(molion)
    assert reply['result'] == {'ok': False, 'error': 'Convert to Structure reads bitmap pictures, not drawings.'}
    assert recognizer.seen == []


def test_nothing_recognised_says_how_to_help():
    molion = FakeMolion({'scene:get-image': picture()})
    reply, _ = run(molion, recognizer=FakeRecognizer(Structure()))
    assert reply['result']['ok'] is False
    assert 'Crop it to one molecule' in reply['result']['error']
    assert molion.calls('scene:delete') == []


def test_a_picture_that_is_not_a_structure_changes_nothing():
    noise = Structure(ETHANOL.atoms, ETHANOL.bonds, confidence=0.3)
    molion = FakeMolion({'scene:get-image': picture()})
    reply, _ = run(molion, recognizer=FakeRecognizer(noise))
    assert 'No structure found' in reply['result']['error']
    assert molion.calls('scene:delete') == []


def test_an_unsure_recognition_asks_the_user_to_check():
    unsure = Structure(ETHANOL.atoms, ETHANOL.bonds, confidence=0.7)
    reply, _ = run(FakeMolion({'scene:get-image': picture()}), recognizer=FakeRecognizer(unsure))
    assert 'Check the structure' in reply['result']['message']


def test_the_first_time_it_asks_then_downloads_with_progress():
    store = FakeStore(ready=False)
    molion = FakeMolion({'scene:get-image': picture(), 'dialog': {'cancelled': False, 'values': {}}})
    reply, _ = run(molion, store=store)
    assert reply['result']['ok'] is True
    [dialog] = molion.calls('dialog')
    assert dialog['title'] == 'Download Recognition Model'
    assert '310 MB' in dialog['fields'][0]['text']
    assert store.downloads == 1
    progress = [m['params'] for m in molion.sent if m.get('method') == 'progress']
    assert progress[0] == {'message': 'Downloading recognition model', 'fraction': 1.0}
    assert all('id' not in m for m in molion.sent if m.get('method') == 'progress')


def test_declining_the_download_changes_nothing_and_says_nothing():
    store = FakeStore(ready=False)
    molion = FakeMolion({'scene:get-image': picture(), 'dialog': {'cancelled': True, 'reason': 'escape'}})
    reply, recognizer = run(molion, store=store)
    assert reply['result'] == {'ok': False}
    assert store.downloads == 0
    assert recognizer.seen == []
    assert molion.calls('scene:delete') == []


def test_nothing_selected():
    reply, _ = run(FakeMolion(), images=())
    assert reply['result'] == {'ok': False, 'error': 'Select one picture first.'}
