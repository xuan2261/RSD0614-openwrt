# Current bring-up status

## Execution-passed evidence

- UART (`115200 8N1`) and RealTek `RTL8197F-VG` bootloader (`version:586`) command mode on the physical RSD0614 (`AUTOBURN 0`, `LOADADDR 81000000`, `J 81000000`).
- 64 MiB DDR2 (`533 MHz`) and 8 MiB `BH25Q64` (`JEDEC 684017`, `64 KiB` erase) NOR identity.
- SoC identity confirmed in hardware at runtime: `BOOTSTRAP = 81970001 0 41258ee0 80003800` (`soc_id = 0x81970001`, **RTL8197FH-VG**).
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) verified on physical Rock Space RSD0614 V1.0**:
  - `dw8250` runtime SoC-ID dispatch selected standard 16550/DW-APB mode (`soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0`).
  - Bidirectional `ttyS0` (`16550A` at `0x18147000`, `irq = 17`) console and interactive BusyBox `ash` root shell verified (`/proc/interrupts` `17: 102 SOC 9 ttyS0`, `ERR: 0`).

## v5.4.0 scope — Read-Only SPI NOR (`BH25Q64`) qualification

Now that `ttyS0` and interactive RAM-boot userspace are hardware-proven:
- Retire diagnostic `keep_bootcon` from `bootargs` so console output is single-stream on `ttyS0` while keeping `initcall_debug ignore_loglevel`.
- Enable `&spi0 { status = "okay"; };` (`spi-max-frequency = <25000000>`, capped to conservative `clk_div >= 28` ~8 MHz by bounded-timeout `spi-sheipa.c` with `WRDI` init).
- Probe `BH25Q64` (`0x684017`, `64 KiB * 128 = 8 MiB`) using conservative single-lane `SPI_NOR_NO_FR | SPI_NOR_SKIP_SFDP` (`0x2008`).
- Enforce all 6 fixed partitions (`bootloader`, `cfg`, `firmware`, `cpe`, `cfm`, `cfm_backup`) as strictly `read-only;`, keep `CONFIG_MTD_SPLIT_FIRMWARE` and `CONFIG_MTD_SPLIT_CVIMG_FW` disabled, and keep all `mount_root` paths suppressed.
- Keep `ethernet`, `pcie0`, `pcie1`, and `wmac` `disabled`.

Expected hardware validation on RSD0614:
- `m25p80 spi0.0: bh25q64 (8192 Kbytes)` probed cleanly without controller timeout;
- `/proc/mtd` lists `mtd0..mtd5` matching the exact 6 read-only stock partitions;
- read-only inspection (`head -c 16 /dev/mtd0ro | hexdump -C`, verifying `mtd` `flags` lack `MTD_WRITEABLE`) succeeds cleanly from RAM without any write capability.

## Verification boundary

- v5.3.9 serial-only RAM-boot & interactive `ttyS0` shell on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.4.0 preflight/build/runtime (`spi0` / `BH25Q64` read-only MTD probe): **NOT YET VERIFIED**.
- Disabled board peripherals (`ethernet` / `RTL8367RB`, `pcie0` / `RTL8814BR`, `wmac`, LEDs/buttons): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
