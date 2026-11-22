# Current bring-up status

## Execution-passed evidence

- UART (`115200 8N1`) and RealTek `RTL8197F-VG` bootloader (`version:586`) command mode on the physical RSD0614 (`AUTOBURN 0`, `LOADADDR 81000000`, `J 81000000`).
- 64 MiB DDR2 (`533 MHz`) and 8 MiB `BH25Q64` (`JEDEC 684017`, `64 KiB` erase) NOR identity.
- SoC identity confirmed in hardware at runtime: `BOOTSTRAP = 81970001 0 41258ee0 80003800` (`soc_id = 0x81970001`, **RTL8197FH-VG**).
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) RAM-boot candidate (`sha256: e8199f3abde18b91c460df6eef265218226e33fb6bbad2a3fb09b1219ad65768`, `2,928,560` / `0x2CAFB0` bytes) verified on physical Rock Space RSD0614 V1.0**:
  - `dw8250` runtime SoC-ID dispatch selected standard 16550/DW-APB mode:
    `dw-apb-uart 18147000.serial: rtl8197f-uart: soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0`
  - Clean `ttyS0` registration and bidirectional console handoff (`18147000.serial: ttyS0 at MMIO 0x18147000 (irq = 17, base_baud = 6250000) is a 16550A`); duplicate kernel log lines after `console [ttyS0] enabled` confirm both `early0` and `ttyS0` transmitting simultaneously under diagnostic `keep_bootcon`.
  - `sheipa_spi_init` returned `-19` (`-ENODEV`), confirming `spi0` stayed unprobed as intended.
  - Interactive OpenWrt BusyBox `ash` root shell activated cleanly via UART (`Enter`), confirming:
    - `/etc/rsd0614-diagnostic-mode` -> `v5.3.9-uart-soc-id-dispatch`
    - `/tmp/sysinfo/model` -> `Rock Space RSD0614 V1.0`
    - `/proc/interrupts` -> `7: 22199 MIPS 7 timer`, `17: 102 SOC 9 ttyS0`, `ERR: 0` (zero IRQ17 storm, zero spurious `rtl8197f-uart-diag` trigger).

## Root-cause resolution summary

v5.3.7 hardware snapshot (`timeout=441/512`, `lsr=61`, `rbr=00`, `iir=cc->rx:cc`, `lcr=13`) was caused by OpenWrt base patch `0004-rtl8197f-dw-uart.patch` unconditionally forcing non-VG `RTL8197F` (`0x8197F000`) quirks (`tx_reg = rx_reg = 9 (+0x24)`, `adjlcr = true`) onto **RTL8197FH-VG** (`0x81970001`, standard `+0x00` RBR/THR and `WLEN8 = 0x03`).

v5.3.9 resolved this structurally via:
- runtime SoC-ID dispatch from `realtek,rtl819x-sysc` (`0x00`): `vg-std` (`0x81970xxx`) vs `non-vg` (`0x8197Fxxx`);
- pre-write `rtl8197f_translate_lcr()` in `dw8250_serial_out{,32,32be}` before MMIO write (eliminating spurious `dw8250_force_idle()` FIFO resets);
- preserving `UPF_SHARE_IRQ | UPF_FIXED_PORT` (`p->flags |= UPF_SKIP_TEST | UPF_FIXED_TYPE`) without setting `p->fifosize` in probe;
- retaining `is_rtl8197f`-guarded BUSY LCR replay and bounded IRQ diagnostics.

## Verification boundary

- v5.3.9 preflight (`45031113801`) & full compile/offline structural audit (`45026415476` at commit `221aae1`): **PASS**.
- v5.3.9 serial-only RAM-boot & interactive `ttyS0` shell on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- Disabled board peripherals (`spi0` / `BH25Q64` read-only MTD probe, `ethernet` / `RTL8367RB`, `pcie0` / `RTL8814BR`, `wmac`, LEDs/buttons): **NOT YET VERIFIED** (kept disabled until dedicated per-subsystem RAM-boot milestones).
- Persistent flash: **NO-GO**.
