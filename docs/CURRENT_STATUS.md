# Current bring-up status

## Execution-passed evidence

- UART and RealTek bootloader command mode on the physical RSD0614.
- 64 MiB RAM and 8 MiB BH25Q64 NOR identity.
- Full 8 MiB stock backup read twice with identical SHA-256 (backup is intentionally not in this repository).
- TFTP PUT/GET and RAM integrity at `0x81000000` with `AUTOBURN 0`.
- Linux 4.14.187 reaches `Rock Space RSD0614 V1.0`, recognizes 64 MiB RAM, completes kernel init, and reaches OpenWrt `procd` userspace.
- `keep_bootcon` proved the earlier apparent stop at the 8250 handoff was console visibility, not a kernel hang.
- v5.3.6 compiled and independently audited the BUSY USR+LCR replay into machine code.

## Current blocker

v5.3.6 still fails interactive UART RX: the first user input is followed by a persistent
`serial8250: too much work for irq17` storm. This falsifies BUSY-replay as a sufficient fix.

The Linux 8250 shared-IRQ loop emits that warning only after the port handler continues to
report an interrupt pending for more than PASS_LIMIT passes. The remaining unknown is the
actual IIR source that stays asserted: MSI, THRI, RDI, RLSI, BUSY, RX timeout, or another ID.

## v5.3.7 diagnostic scope

- Preserve the exact v5.3.6 UART behavior and safety boundary.
- For the first 511 RTL8197F handler passes, only count IIR IDs; do not perform extra register reads.
- At pass 512, take one ordered snapshot:
  - read IIR baseline;
  - read LSR and re-read IIR;
  - read MSR and re-read IIR;
  - read USR and re-read IIR;
  - read RX and re-read IIR.
- Also capture IER, LCR, RTL8197F status register (index 8), and saved `last_lcr`.
- Emit only two bounded messages through `printk_deferred()` to avoid recursively driving the UART console from the ISR.
- Use a fresh v5.3.7 build volume.

The IIR transition identifies the clear-source:
- clears after LSR: line-status source;
- clears after MSR: modem-status source;
- clears after USR: DesignWare BUSY source;
- clears after RX: receive-data / stale receive-timeout source;
- remains pending after all reads: investigate TX/IER/controller semantics next.

## Verification boundary

- v5.3.4 interactive UART RX: FAIL (IRQ17 storm).
- v5.3.5: compile FAIL due patch-order conflict.
- v5.3.6 compile/offline audit: PASS; hardware interactive UART RX: FAIL.
- v5.3.7 preflight/build/hardware diagnostic: NOT YET VERIFIED.
- Persistent flash: NO-GO.
