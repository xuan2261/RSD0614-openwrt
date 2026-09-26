# Current bring-up status

## Execution-passed evidence

- UART and RealTek bootloader command mode on the physical RSD0614.
- 64 MiB RAM and 8 MiB BH25Q64 NOR identity.
- Full 8 MiB stock backup read twice with identical SHA-256 (backup is intentionally not in this repository).
- TFTP PUT/GET and RAM integrity at `0x81000000` with `AUTOBURN 0`.
- First OpenWrt initramfs candidate: loader decompressed successfully, Linux 4.14.187 started, machine identified as `Rock Space RSD0614 V1.0`, 64 MiB RAM recognized, serial console enabled.

## Current blocker

The first kernel stopped producing output immediately after the 8250 console handoff and before userspace. The next diagnostic build disables `spi0` and enables `initcall_debug ignore_loglevel` to test whether the RTL8197F Sheipa SPI/NOR probe is the blocker.

## Verification boundary

- v5.3 diagnostic design/local regression: PASS.
- v5.3 GitHub/local Docker compile: not yet established in this repository.
- v5.3 physical RAM boot: NOT YET VERIFIED.
- Persistent flash: NO-GO.
