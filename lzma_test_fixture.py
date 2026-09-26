"""Immutable, synthetic LZMA fixture; not router data and not a firmware image."""
from pathlib import Path
import hashlib,struct
FIXTURE=Path(__file__).resolve().parent/'fixtures/linux-known-size-no-eopm.lzma';FIXTURE_SHA256='bdfebb29df5e0f4d53972da8ae307e773345d1731b635ef7b55113a6a9792e07';PAYLOAD_SHA256='b34a977c818aa2351e56c17981b69687d38399b57bd4bef580c5469fa038cac1'
def payload_bytes():return b'Linux version fixture\0'+bytes(range(256))*300
def load_fixture(path=None):
    data=(FIXTURE if path is None else Path(path)).read_bytes()
    if len(data)!=344 or hashlib.sha256(data).hexdigest()!=FIXTURE_SHA256:raise ValueError('Synthetic LZMA fixture integrity mismatch; do not skip the test')
    if struct.unpack_from('<Q',data,5)[0]!=len(payload_bytes()):raise ValueError('Synthetic LZMA fixture decoded-size mismatch')
    return data
