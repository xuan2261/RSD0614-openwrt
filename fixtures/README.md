# Portable synthetic LZMA fixture

`linux-known-size-no-eopm.lzma` is **test data, not router firmware**.

- Compressed length: 344 bytes.
- SHA-256: `bdfebb29df5e0f4d53972da8ae307e773345d1731b635ef7b55113a6a9792e07`.
- Uncompressed length: 76,822 bytes.
- Payload: `b"Linux version fixture\0" + bytes(range(256)) * 300`.
- Uncompressed SHA-256: `b34a977c818aa2351e56c17981b69687d38399b57bd4bef580c5469fa038cac1`.
- Header: properties 93, dictionary 8 MiB, explicit uncompressed length.
- No end-of-payload marker. The size is authoritative for stream termination.
- Generated with liblzma 5.8.1, LZMA1EXT, ext_flags=0, preset6.
- Decoded byte-for-byte successfully with actual liblzma5.2.2 and5.8.1.

The development-only generator is `tools/make_lzma_fixture.c`. It verifies the
compressed raw stream with LZMA1EXT's strict no-EOPM decoder before saving it.
The **generator is not run by the Bullseye builder or test suite**; old readers
only need to read the stored standard LZMA-alone fixture.

Different encoder versions may produce different valid compressed bytes. A fixture
update must intentionally update the hash and re-run the real compatibility matrix.
Never silently regenerate it during tests.

## Linux v4.14.187 UART patch contexts

`fixtures/linux-4.14.187/` contains exact upstream source fixtures from the
Linux stable `v4.14.187` tag for:

- `include/uapi/linux/serial_reg.h`
- `drivers/tty/serial/8250/8250_dw.c`

They are test inputs only. The regression suite copies them to a temporary
directory and requires the RSD0614 UART patch to apply with `patch --fuzz=0`.
This catches malformed hunks or upstream-context drift before a full OpenWrt
compile. These files are never installed in the initramfs and never executed on
the router.

## OpenWrt RTL8197F UART patch-stack fixture

`fixtures/openwrt-realtek/0004-rtl8197f-dw-uart.patch` is the exact base
patch from the pinned OpenWrt source commit. The UART regression applies:

1. upstream Linux `v4.14.187` `8250_dw.c`;
2. the pinned OpenWrt Realtek `0004` patch with `--fuzz=0`;
3. the local `9998-rtl8197f-uart-busy-replay.patch` with `--fuzz=0`.

This models the actual OpenWrt patch order and prevents a patch that only applies
to vanilla Linux from passing preflight. The fixture is test-only and is never
installed in the firmware.

