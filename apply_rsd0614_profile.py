#!/usr/bin/env python3
"""Apply only the RSD0614 device profile to the pinned donor; validate before writing."""
from pathlib import Path
import argparse
import os
import re
import subprocess
import tempfile

EXPECTED_DONOR_COMMIT = "229536d89c25a676417717304fcef386a53a7875"
DEVICE_BLOCK = r"""
define Device/RSD0614
  $(Device/RealtekDTS)
  BLOCKSIZE := 64k
  DEVICE_DTS := RSD0614
  DEV_PROFILE := RSD0614
  DEVICE_TITLE := Rock Space RSD0614 V1.0
  SUPPORTED_DEVICES := rockspace-rsd0614 rsd0614
  IMAGE_SIZE := 7808k
  CMDLINE := console=ttyS0,115200
  KERNEL := kernel-bin | append-dtb | lzma | loader-cmdline-compile
  # No factory.bin or sysupgrade.bin pipelines are authorized by this profile.
  IMAGES :=
  DEVICE_PACKAGES :=
endef
TARGET_DEVICES += RSD0614

"""


def code_lines(text: str) -> str:
    """Our generated Make fragment contains no quoted '#'; strip Make comments."""
    return "\n".join(line.split('#', 1)[0].rstrip() for line in text.splitlines())


def validate_profile(block: str) -> None:
    code = code_lines(block)
    if len(re.findall(r'^define Device/RSD0614\s*$', code, re.M)) != 1:
        raise ValueError('Expected exactly one RSD0614 device definition')
    if re.search(r'\b(?:factory|sysupgrade)\.bin\b|IMAGE/|dlink-md5-sign|AUTOBURN\s+1', code):
        raise ValueError('Persistent-image directive in executable Make code')
    images = re.findall(r'^\s*IMAGES\s*([^\n]*)$', code, re.M)
    if images != [':=']:
        raise ValueError('IMAGES must be assigned an empty value exactly once')
    packages = re.findall(r'^\s*DEVICE_PACKAGES\s*([^\n]*)$', code, re.M)
    if packages != [':=']:
        raise ValueError('DEVICE_PACKAGES must remain empty for this first profile')
    parents = re.findall(r'\$\(Device/([^)]+)\)', code)
    if parents != ['RealtekDTS']:
        raise ValueError('Unexpected inherited donor profile')
    required = ('DEVICE_DTS := RSD0614', 'DEV_PROFILE := RSD0614',
                'CMDLINE := console=ttyS0,115200', 'DEVICE_PACKAGES :=')
    for item in required:
        if item not in code:
            raise ValueError(f'Missing required setting: {item}')


def patch_text(original: str) -> str:
    validate_profile(DEVICE_BLOCK)
    pattern = re.compile(r'^define Device/RSD0614\s*\n.*?^endef\s*\n^TARGET_DEVICES \+= RSD0614\s*$', re.M | re.S)
    matches = list(pattern.finditer(original))
    if matches:
        if len(matches) != 1:
            raise ValueError('Duplicate RSD0614 profiles')
        current = matches[0].group(0)
        validate_profile(current)
        if code_lines(current).strip() != code_lines(DEVICE_BLOCK).strip():
            raise ValueError('Existing RSD0614 profile differs; refusing silent replacement')
        return original
    if 'define Device/RSD0614' in original:
        raise ValueError('Malformed existing RSD0614 profile')
    anchor = 'define Device/GWR1200AC\n'
    if original.count(anchor) != 1:
        raise ValueError('Expected unique donor anchor not found')
    return original.replace(anchor, DEVICE_BLOCK + anchor, 1)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def apply_profile(repo: Path, port: Path, expected_commit: str = EXPECTED_DONOR_COMMIT) -> None:
    repo, port = repo.resolve(), port.resolve()
    if not (repo / '.git').is_dir():
        raise ValueError('Not a dedicated Git checkout')
    actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected_commit:
        raise ValueError(f'Unexpected revision: expected {expected_commit}; got {actual}')
    mk = repo / 'files/target/linux/realtek/image/Makefile'
    destination = repo / 'files/target/linux/realtek/dts/RSD0614.dts'
    dts = (port / 'RSD0614.dts').read_bytes()
    original = mk.read_text(encoding='utf-8')
    updated = patch_text(original)  # no file modifications before all profile checks pass
    if destination.exists() and destination.read_bytes() != dts:
        raise ValueError('Existing RSD0614.dts differs; inspect before replacing')
    atomic_write(destination, dts)
    if updated != original:
        atomic_write(mk, updated.encode('utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', required=True, type=Path)
    ap.add_argument('--port-dir', required=True, type=Path)
    args = ap.parse_args()
    try:
        apply_profile(args.repo, args.port_dir)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'PROFILE FAIL: {exc}')
        return 1
    print('PROFILE PASS: pinned checkout; initramfs-only profile; no persistent-image pipeline')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
