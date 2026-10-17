"""Downloads from a local HTTP server: nothing here reaches the internet."""

import hashlib
import http.server
import os
import threading

import pytest

from p2s.model_store import MODEL_DIR_ENV, ModelError, ModelFile, ModelStore

PAYLOADS = {'encoder.onnx': b'e' * 3000, 'decoder.onnx': b'd' * 5000}


@pytest.fixture
def server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = PAYLOADS.get(self.path.lstrip('/'))
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}/'
    httpd.shutdown()


def files(base, damaged=None):
    return tuple(ModelFile(name, base + name, len(body),
                           hashlib.sha256(b'x' if name == damaged else body).hexdigest())
                 for name, body in PAYLOADS.items())


@pytest.fixture(autouse=True)
def no_override(monkeypatch):
    monkeypatch.delenv(MODEL_DIR_ENV, raising=False)


def test_downloads_checks_and_marks_the_folder(server, tmp_path):
    store = ModelStore(str(tmp_path), files(server))
    seen = []
    assert not store.ready()
    folder = store.download(lambda message, fraction: seen.append(fraction))
    assert store.ready()
    assert folder == os.path.join(str(tmp_path), 'model-v1')
    assert open(os.path.join(folder, 'decoder.onnx'), 'rb').read() == PAYLOADS['decoder.onnx']
    assert seen[-1] == 1.0
    assert seen == sorted(seen)
    assert not os.path.exists(folder + '.part')


def test_a_damaged_file_leaves_nothing_behind(server, tmp_path):
    store = ModelStore(str(tmp_path), files(server, damaged='decoder.onnx'))
    with pytest.raises(ModelError, match='damaged'):
        store.download(lambda *_: None)
    assert not store.ready()
    assert os.listdir(tmp_path) == []


def test_a_missing_file_is_a_model_error(server, tmp_path):
    store = ModelStore(str(tmp_path), (ModelFile('gone.onnx', server + 'gone.onnx', 10, '0' * 64),))
    with pytest.raises(ModelError, match='Could not download'):
        store.download(lambda *_: None)
    assert os.listdir(tmp_path) == []


def test_an_unpublished_model_says_so(tmp_path):
    with pytest.raises(ModelError, match='not published'):
        ModelStore(str(tmp_path), ()).download(lambda *_: None)


def test_without_a_data_folder_there_is_nowhere_to_keep_it(server):
    store = ModelStore(None, files(server))
    assert not store.ready()
    with pytest.raises(ModelError, match='no folder'):
        store.download(lambda *_: None)


def test_a_local_model_folder_overrides_the_download(tmp_path, monkeypatch):
    monkeypatch.setenv(MODEL_DIR_ENV, str(tmp_path))
    store = ModelStore(None, ())
    assert store.ready()
    assert store.folder == str(tmp_path)


def test_the_systems_own_certificates_are_loaded_for_https(tmp_path):
    # What makes the download work in a frozen build on a machine without the build
    # machine's Python: the operating system's bundle, found and loaded.
    import ssl
    from p2s.model_store import CA_BUNDLES, make_context
    bundle = next((path for path in CA_BUNDLES if os.path.isfile(path)), None)
    if bundle is None:
        pytest.skip('no system certificate bundle here (Windows reads its own store)')
    empty = make_context(bundles=())
    loaded = make_context(bundles=(str(tmp_path / 'missing.pem'), bundle))
    assert len(loaded.get_ca_certs()) > 0
    assert len(loaded.get_ca_certs()) >= len(empty.get_ca_certs())
    assert isinstance(loaded, ssl.SSLContext)
