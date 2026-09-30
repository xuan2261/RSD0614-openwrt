# Current bring-up status

## Execution-passed evidence

- UART and RealTek bootloader command mode on the physical RSD0614.
- 64 MiB RAM and 8 MiB BH25Q64 NOR identity.
- Full 8 MiB stock backup read twice with identical SHA-256 (backup is intentionally not in this repository).
- TFTP PUT/GET and RAM integrity at `0x81000000` with `AUTOBURN 0`.
- Linux 4.14.187 reaches `Rock Space RSD0614 V1.0`, recognizes 64 MiB RAM, completes kernel init, and reaches OpenWrt `procd` userspace.
- `keep_bootcon` proved the earlier apparent stop at the 8250 handoff was console visibility, not a kernel hang.
- v5.3.4 proved interactive UART input still causes an IRQ17 storm.
- v5.3.5 preflight passed but full compile failed because the custom UART patch was authored against vanilla Linux 4.14.187 while OpenWrt applies `0004-rtl8197f-dw-uart.patch` first.

## Root cause refinement

OpenWrt base patch `0004-rtl8197f-dw-uart.patch` already supplies the RTL8197F-specific dynamic RX/TX register mapping (index 9), `adjlcr` line-control adjustment, fixed `PORT_16550A`, and skip-autoconfig behavior.

Therefore changing global `serial_reg.h` RX/TX/WLEN values is not only redundant but can double-apply the RTL8197F line-control transformation.

Vendor RTL8197F code differs from OpenWrt `0004` in one important BUSY path: after reading the DesignWare USR to clear BUSY, it replays the last adjusted LCR value. v5.3.6 ports only this missing delta.

## v5.3.6 diagnostic scope

- Preserve OpenWrt base `0004` RX/TX index 9 and `adjlcr` behavior.
- Preserve generic Linux `serial_reg.h` values (`UART_RX/TX=0`, `WLEN8=0x03`).
- Save the hardware-adjusted LCR value.
- On DesignWare BUSY: read USR, then replay the saved LCR.
- Use a fresh v5.3.6 build volume; never reuse the failed v5.3.5 volume.
- Keep SPI, Ethernet, PCIe0/1 and WMAC disabled.
- Keep persistent-root automatic paths suppressed.

## Verification boundary

- v5.3.4 compile/offline audit: PASS.
- v5.3.4 physical boot to userspace: PASS.
- v5.3.4 interactive UART RX: FAIL (IRQ17 storm).
- v5.3.5 preflight: PASS; full build: FAIL at UART patch application.
- v5.3.6 patch-stack preflight/full build/runtime: NOT YET VERIFIED until fresh evidence.
- Persistent flash: NO-GO.
