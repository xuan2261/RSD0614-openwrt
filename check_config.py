#!/usr/bin/env python3
"""Inspect the resolved OpenWrt configuration, not just the seed."""
from pathlib import Path
import re
import sys


def validate(text: str) -> None:
    active = dict(re.findall(r'^(CONFIG_[A-Za-z0-9_+.-]+)=([^\n]+)$', text, re.M))
    for key in ('CONFIG_TARGET_realtek_rtl8197f_DEVICE_RSD0614', 'CONFIG_TARGET_ROOTFS_INITRAMFS'):
        if active.get(key) != 'y':
            raise ValueError(f'Required option not selected: {key}')
    for key, value in active.items():
        if value not in ('y', 'm'):
            continue
        if key.startswith('CONFIG_TARGET_') and '_DEVICE_' in key and not key.endswith('_DEVICE_RSD0614'):
            raise ValueError(f'Unexpected second target: {key}')
        if key in ('CONFIG_TARGET_ALL', 'CONFIG_TARGET_MULTI_PROFILE'):
            raise ValueError(f'Unbounded device selection: {key}')
        if key.startswith('CONFIG_TARGET_ROOTFS_') and key != 'CONFIG_TARGET_ROOTFS_INITRAMFS':
            if not key.startswith('CONFIG_TARGET_ROOTFS_INITRAMFS_'):
                raise ValueError(f'Additional filesystem output enabled: {key}')
        if key.startswith('CONFIG_PACKAGE_'):
            package = key[len('CONFIG_PACKAGE_'):]
            if package.startswith(('kmod-rtw', 'kmod-rtl8192cd', 'rtl8822be-firmware', 'wpad', 'hostapd', 'luci')):
                raise ValueError(f'Donor Wi-Fi/LuCI package selected: {key}={value}')

if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Usage: check_config.py .config')
        validate(Path(sys.argv[1]).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'CONFIG FAIL: {exc}')
        raise SystemExit(1)
    print('CONFIG PASS: RSD0614-only initramfs; no selected donor Wi-Fi/LuCI package')
