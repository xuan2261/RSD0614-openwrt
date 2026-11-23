# Current bring-up status

## Execution-passed evidence

- UART (`115200 8N1`) and RealTek `RTL8197F-VG` bootloader (`version:586`, `999MHz`, `Lan pbmp:0x000000ef`, `Wan pbmp:0x000000f0`, `port[2] link:up`) command mode on the physical RSD0614 (`AUTOBURN 0`, `LOADADDR 81000000`, `J 81000000`).
- 64 MiB DDR2 (`533 MHz`) and 8 MiB `BH25Q64` (`JEDEC 684017`, `EXT id 0x6840`, `64 KiB` erase) NOR identity.
- SoC identity & crystal strap confirmed in hardware at runtime: `BOOTSTRAP = 81970001 0 41258ee0 80003800` (`soc_id = 0x81970001` **RTL8197FH-VG**, `0x41258ee0` `BIT(24)=1` **40 MHz XTAL**, `bits[18:15]=0xb` **1000 MHz CPU**, `BIT(5)=1` **DDR2-533**, `CLKMANAGE=0x80003800` `SWCORE` clock active).
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) verified on physical Rock Space RSD0614 V1.0**:
  - `dw8250` runtime SoC-ID dispatch selected standard 16550/DW-APB mode (`soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0`).
- **v5.4.1 (`v5.4.1-omnibus-readonly-survey`) passive & button survey verified on physical Rock Space RSD0614 V1.0**:
  - Clean `ttyS0` boot without `keep_bootcon` (`MemTotal: 59540 kB`, `MemFree: 49252 kB`, `/proc/interrupts` `irq17=105`, `ERR=0`).
  - `spi0` / `BH25Q64` (`m25p80 spi0.0: bh25q64 (8192 Kbytes)`, `div 28`) and all 6 read-only MTD partitions (`mtd0..mtd5`, `flags=0x800`, `writeable_bit_0x400=0`) verified; stock `mtd2ro` header verified as `cr6c` (`start_addr=0x80a00000`, `burn_addr=0x00030000`, `hdr_len=0x00256c02`).
  - Package & mux/GPIO truth: `SYSC_BOND_OPTION=0x00000004` (`BSP_BOND_97FN`), `PINMUX_SEL2=0x00000000` & `GPIO_PABCD_CNR=0xffffffff` (bootloader uses hardware `P0MDC`/`P0MDIO` rather than pre-muxed GPIO SMI on `C2`/`C3`), `PINMUX_SEL13=0x33320000`, `PINMUX_SEL14=0x20000000` (`H2` = `RTL8367` reset held high in `GPIO_PEFGH_DAT=0x05c00013`), `PINMUX_SEL17=0x10110110`.
  - Physical button verified on **`GPIO_PEFGH` bit 4 (`&gpio1 4 GPIO_ACTIVE_LOW`, `BSP_GPIO_PIN_E4`, `xor=0x00000010`)**.
  - RGMII trunk on `SWCORE` Port 0 verified: `SWCORE_PITCR=0x00000001`, `SWCORE_P0GMIICR=0x00037d57` (`TX_delay=1`, **`RX_delay=7`**, CPU-tag bits off), `SWCORE_PCRP0=0x16972039` (`ExtPHYID=22`, `Pause=3`, `Force 1000M/FD`), `SWCORE_EXTPCR0=0x000c0000`, `PINMUX_RGMII_PAD_CTRL=0x579fff7f`, `SWCORE_PSRP0=0x0000307a`, `MIB_P0 <-> MIB_P6` = `5,731` frames (`0x318dd9` bytes, zero loss).

## v5.4.2 scope — Multi-Bus Switch Discovery + `wmac`/`pcie0` Completion (`v5.4.2-omnibus-readonly-survey`)

In `v5.4.1`, `rsd0614-survey probe-all` halted right after `smi` (`skipped_pinmux_mismatch`) because BusyBox `printf "%s\n"` flushed the trailing `\n` in a separate 1-byte `write()`, which `rsd0614_probe_write` rejected with `-EINVAL` under `set -e`. `v5.4.2` resolves all three findings in one fast cached build:
- **Split-newline tolerance**: `/proc/rsd0614_probe` ignores empty/whitespace-only writes (`if (*cmd == '\0') return count;`) and `rsd0614-survey` writes tokens without trailing `\n`, so `probe-all` runs `smi` -> `wmac` -> `pcie0` end-to-end.
- **Instant `cvimg` rootfs offset probe**: replaces the 140-second 8 MiB `hexdump` scan in `rsd0614-survey passive` with a `<0.05s` targeted check at `ALIGN(16 + hdr_len, 4)` and `4K`/`64K` boundaries.
- **Safe 3-way `RTL8367` management bus auto-discovery (`smi`)**:
  1. `SWCORE` Clause-22 MDIO scan (`phy 0..31` `reg 2/3`) + indirect `RTL8367` read (`phy 0, 29, PCRP0 ExtPHYID=22`) via `MDCIOCR`/`MDCIOSR` (`0xBB804004`/`0xBB804008`);
  2. 2-wire SMI on `PABCD` `18/19` (`C2/C3`) with temporary `PINMUX_SEL2[11:4]=0x66` & `PABCD_CNR[19:18]=0`, unconditionally restoring `PABCD_DAT/DIR/CNR` and `PINMUX_SEL2` afterward;
  3. 2-wire SMI on `PEFGH` `23/24` (`G7/H0`, already `CNR=0, DIR=IN, DAT=1`), restoring `PEFGH_DAT/DIR` bits `23..24` and never touching bit `26` (`PH2` hardware reset) or `0x1322`.

## Consolidated Roadmap (M1 -> M2 -> M3)

1. **M1b (`v5.4.2` — this build)**: Run `rsd0614-survey probe-all` (or `printf %s wmac > /proc/rsd0614_probe; printf %s pcie0 > /proc/rsd0614_probe` if `v5.4.1` is still live) to lock in `RTL8367` management bus + `WMAC` cut/HAL + `PCIe0` `10ec:b814` link-up.
2. **M2 (Functional RAM-boot router)**: Enable `&ethernet` (preserving RSD0614's hardware-verified `P0GMIICR=0x00037d57` RX delay `7`, `EXTPCR0=0x000c0000`, `RGMII_PAD_CTRL=0x579fff7f` + `RTL8367RB` LAN `0..3` / WAN `4` VLANs), `&gpio1 4` button, `&pcie0` 40 MHz bus, and 2.4 GHz `WMAC` (`0x81970001` VG ID + `97FN` bond `0x4` + `/dev/mtd1ro` calibration) in one consolidated RAM-boot build.
3. **M3 (`RTL8814BR` `10ec:b814` 5 GHz driver)**: Integrate `RTL8814B` (`10ec:b814`) driver support.

## Verification boundary

- v5.3.9 & v5.4.1 `ttyS0` shell, `spi0` `BH25Q64` read-only MTDs, passive `SYSC`/`PINMUX`/`GPIO`/`SWCORE` register survey, and `GPIO1_4` button on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.4.2 multi-bus `smi` + `wmac` + `pcie0` probes on physical RSD0614 V1.0 UART/runtime: **NOT YET VERIFIED**.
- Disabled board peripherals (`ethernet` / `RTL8367RB`, `pcie0` / `RTL8814BR`, `wmac`, LEDs): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
