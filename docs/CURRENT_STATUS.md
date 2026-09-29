# Current bring-up status

## Execution-passed evidence

- UART and RealTek bootloader command mode on the physical RSD0614.
- 64 MiB RAM and 8 MiB BH25Q64 NOR identity.
- Full 8 MiB stock backup read twice with identical SHA-256 (backup is intentionally not in this repository).
- TFTP PUT/GET and RAM integrity at `0x81000000` with `AUTOBURN 0`.
- Linux 4.14.187 reaches `Rock Space RSD0614 V1.0`, recognizes 64 MiB RAM, completes kernel init, and reaches OpenWrt `procd` userspace.
- `keep_bootcon` proved the earlier apparent stop at the 8250 handoff was console visibility, not a kernel hang.
- v5.3.4 proved the compiled 8250 code used RTL8197F RX/TX register index 9, but hardware input still produced a sustained IRQ17 storm.

## Current blocker

Interactive UART RX is not yet qualified. On the v5.3.4 RAM-only candidate, the first UART input triggers repeated
`serial8250: too much work for irq17`.

The partial RX/TX-offset port is therefore insufficient. Vendor RTL8197F evidence also requires its line-control encoding and DesignWare BUSY recovery semantics. v5.3.5 ports those remaining UART semantics while preserving the RAM-only safety boundary.

## v5.3.5 diagnostic scope

- RTL8197F RX/TX register index 9 (`+0x24` with `reg-shift=2`).
- RTL8197F vendor WLEN encoding (`WLEN8=0x01`).
- Fixed `PORT_16550A`, FIFO16, skip-autoconfig profile for `realtek,rtl8197f-uart`.
- DesignWare BUSY recovery: read USR, then replay the last LCR value.
- Generic Linux 4.14.187 RX-timeout workaround remains intact.
- SPI, Ethernet, PCIe0/1 and WMAC remain disabled.
- Persistent-root auto paths remain suppressed.

## Verification boundary

- v5.3.4 compile/offline audit: PASS.
- v5.3.4 physical boot to userspace: PASS.
- v5.3.4 interactive UART RX: FAIL (IRQ17 storm).
- v5.3.5 source/regression/build/runtime: NOT YET VERIFIED until fresh CI and hardware evidence.
- Persistent flash: NO-GO.
