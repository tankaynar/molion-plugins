#!/usr/bin/env python3
"""Picture to Structure — a Molion plugin: a picture of a molecule becomes a structure.

It contributes one action, Convert to Structure, offered while one picture is selected. The
picture is read with MolScribe (an ONNX export, run by onnxruntime on this computer) and
replaced by the molecule, laid out as it was drawn. The model is downloaded the first time,
after the user agrees, into the data folder Molion gives the plugin; pictures never leave the
computer.

    python3 main.py

The protocol: Molion's plugin protocol, newline-delimited JSON-RPC 2.0 on stdin/stdout.
Logs go to stderr only; stdout is the channel.

In a development run the system Python usually lacks onnxruntime, numpy and Pillow. If a
`.venv` beside this file has them, the plugin restarts itself with that interpreter.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
sys.path.insert(0, HERE)

PROTOCOL_VERSION = 1


def _venv_python() -> str | None:
    if getattr(sys, 'frozen', False):
        return None
    candidate = (os.path.join(HERE, '.venv', 'Scripts', 'python.exe') if os.name == 'nt'
                 else os.path.join(HERE, '.venv', 'bin', 'python'))
    if not os.path.isfile(candidate):
        return None
    if os.path.realpath(sys.prefix) == os.path.realpath(os.path.join(HERE, '.venv')):
        return None                           # already running in it
    return candidate


def _maybe_reexec() -> None:
    try:
        import onnxruntime  # noqa: F401
        return
    except ImportError:
        pass
    python = _venv_python()
    if python:
        os.execv(python, [python, os.path.abspath(__file__), *sys.argv[1:]])


from p2s.convert import Converter        # noqa: E402
from p2s.model_store import ModelStore   # noqa: E402
from p2s.rpc import Host, log            # noqa: E402


def load_recognizer(folder: str):
    # Imported here: onnxruntime, numpy and Pillow load only when a picture is converted.
    from p2s.recognizer import OnnxRecognizer
    return OnnxRecognizer(folder)


def serve(host: Host, load=load_recognizer) -> int:
    """Answers each request until shutdown or end of input."""
    converter: Converter | None = None
    while True:
        line = host.readline()
        if not line:
            return 0
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            log('ignored a line that is not JSON')
            continue
        method, request_id = message.get('method'), message.get('id')
        if method is None:
            continue
        params = message.get('params') or {}
        try:
            if method == 'initialize':
                converter = Converter(host, ModelStore(params.get('dataDir')), load)
                result = {'name': 'Picture to Structure', 'version': '1.0.0',
                          'protocolVersion': PROTOCOL_VERSION}
            elif method == 'invoke':
                if converter is None:
                    converter = Converter(host, ModelStore(None), load)
                result = converter.invoke(params)
            elif method == 'shutdown':
                return 0
            else:
                result = {}
        except Exception as error:
            log(traceback.format_exc())
            if request_id is not None:
                host.reply(request_id, error=str(error))
            continue
        if request_id is not None:
            host.reply(request_id, result)


def check_runtime() -> int:
    """For checking a frozen build: whether the libraries recognition needs load here, and
    whether the model's download can verify HTTPS (0 root certificates: it never can)."""
    import numpy
    import onnxruntime
    import PIL
    from p2s.model_store import ca_certificate_count
    certificates = ca_certificate_count()
    print(f'onnxruntime {onnxruntime.__version__}, numpy {numpy.__version__}, Pillow {PIL.__version__}, '
          f'{certificates} root certificates')
    return 0 if certificates else 1


def main() -> int:
    _maybe_reexec()
    if '--check-runtime' in sys.argv:
        return check_runtime()
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')

    def write(message: dict) -> None:
        sys.stdout.write(json.dumps(message, ensure_ascii=False) + '\n')
        sys.stdout.flush()

    return serve(Host(sys.stdin.readline, write))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (BrokenPipeError, KeyboardInterrupt):
        pass
