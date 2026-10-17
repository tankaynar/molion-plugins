"""The one way this plugin reaches the network: HTTPS GETs to PubChem.

Molion runs the plugin only once the user has turned it on (Settings → Plugins), and grants it
the network for that (its `network` capability); Molion itself never goes online.
"""

from __future__ import annotations

import os
import ssl
import sys
import urllib.request

USER_AGENT = 'Molion-PubChem/1.0'

# Where operating systems keep their root certificates as one PEM file: macOS (the system
# bundle Apple maintains), Debian/Ubuntu/Arch, Fedora/RHEL, openSUSE, Alpine.
CA_BUNDLES = (
    '/etc/ssl/cert.pem',
    '/etc/ssl/certs/ca-certificates.crt',
    '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem',
    '/etc/pki/tls/certs/ca-bundle.crt',
    '/etc/ssl/ca-bundle.pem',
)


def make_context(bundles=CA_BUNDLES) -> ssl.SSLContext:
    # A frozen build's OpenSSL looks for certificates where the build machine's Python kept
    # them (a python.org framework path on macOS), which does not exist on users' machines, so
    # every request would fail verification in packaged builds only. The operating system's own
    # bundle is loaded as well. Windows needs nothing: Python reads its certificate store.
    context = ssl.create_default_context()
    if sys.platform != 'win32':
        for path in bundles:
            if os.path.isfile(path):
                try:
                    context.load_verify_locations(cafile=path)
                    break
                except (OSError, ssl.SSLError):
                    continue
    return context


_context = None


def ca_certificate_count() -> int:
    """How many root certificates HTTPS can verify against; 0 means no request can succeed."""
    return len(_get_context().get_ca_certs())


def _get_context() -> ssl.SSLContext:
    global _context
    if _context is None:
        _context = make_context()
    return _context


def fetch(url: str, timeout: float) -> bytes:
    """GET `url` and return the body. Raises urllib's errors: HTTPError for a 404, URLError
    when PubChem cannot be reached."""
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=_get_context()) as response:
        return response.read()
