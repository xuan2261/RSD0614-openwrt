#!/usr/bin/env python3
"""Basic artifact screening only. A passed screen NEVER authorizes a RAM boot."""
from pathlib import Path
import argparse,hashlib
def screen(data:bytes,name:str)->list:
    errors=[]
    if not ('rsd0614' in name.lower() and 'initramfs' in name.lower()):errors.append('Unexpected candidate filename')
    if not 0x10000<=len(data)<=0x1000000:errors.append('Outside the preliminary 64 KiB..16 MiB file-size budget')
    if data and len(set(data))<=1:errors.append('Uniform data is not a plausible kernel/loader')
    if data[:4] in (b'cr6b',b'cr6c',b'cs6c',bytes.fromhex('27051956')):errors.append('Unexpected vendor/container header at offset zero')
    if data[-4:]==bytes.fromhex('00c0ffee'):errors.append('Unexpected D-Link persistent-image trailer')
    return errors
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('image',type=Path);args=ap.parse_args()
    try:
        size=args.image.stat().st_size
        if size>0x1000000:raise ValueError('Candidate exceeds screening memory limit')
        data=args.image.read_bytes();errors=screen(data,args.image.name)
    except (OSError,ValueError) as exc:print(f'ARTIFACT_SCREEN: FAIL — {exc}');print('RAM_BOOT_AUTHORIZED: NO');return 1
    print(f'file={args.image.name}');print(f'size={len(data)}');print(f'sha256={hashlib.sha256(data).hexdigest()}')
    for error in errors:print(f'FAIL: {error}')
    print('ARTIFACT_SCREEN: '+('FAIL' if errors else 'PASS'));print('BOOT_QUALIFICATION: NOT YET VERIFIED');print('RAM_BOOT_AUTHORIZED: NO');print('Screening does not validate decompression, DTB, entry point, load geometry, or absence of flash writes.');return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
