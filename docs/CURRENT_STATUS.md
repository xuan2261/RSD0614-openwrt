# Current bring-up status

## Execution-passed evidence

- UART (`115200 8N1`) and RealTek `RTL8197F-VG` bootloader (`version:586`, `999MHz`, `Lan pbmp:0x000000ef`, `Wan pbmp:0x000000f0`, `port[2] link:up`) command mode on the physical RSD0614 (`AUTOBURN 0`, `LOADADDR 81000000`, `J 81000000`).
- 64 MiB DDR2 (`533 MHz`) and 8 MiB `BH25Q64` (`JEDEC 684017`, `EXT id 0x6840`, `64 KiB` erase) NOR identity.
- SoC identity & crystal strap confirmed in hardware at runtime: `BOOTSTRAP = 81970001 0 41258ee0 80003800` (`soc_id = 0x81970001` **RTL8197FH-VG**, `0x41258ee0` `BIT(24)=1` **40 MHz XTAL**, `bits[18:15]=0xb` **1000 MHz CPU**, `BIT(5)=1` **DDR2-533**, `CLKMANAGE=0x80003800` `SWCORE` clock active).
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) verified on physical Rock Space RSD0614 V1.0**:
  - `dw8250` runtime SoC-ID dispatch selected standard 16550/DW-APB mode (`soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0`).
  - Bidirectional `ttyS0` (`16550A` at `0x18147000`, `irq = 17`) console and interactive BusyBox `ash` root shell verified (`/proc/interrupts` `17: 102 SOC 9 ttyS0`, `ERR: 0`).

## v5.4.1 scope — Omnibus Read-Only Hardware Qualification (`v5.4.1-omnibus-readonly-survey`)

To eliminate serial rebuild churn while upholding `AGENTS.md` (unverified peripherals disabled at boot; persistent flash `NO-GO`; zero device-unique secret leaks), `v5.4.1` combines build acceleration with an omnibus read-only qualification layer so **one RAM boot** collects all remaining target hardware facts:
- **SPI NOR (`spi0` / `BH25Q64` `0x684017`)**: `keep_bootcon` retired; `&spi0` enabled at conservative single-lane `SPI_NOR_NO_FR | SPI_NOR_SKIP_SFDP` (`0x2008`, `spi-sheipa` `clk_div >= 28` + bounded CP0 WIP timeouts) across 6 `read-only;` MTD partitions (`mtd0..mtd5`), with `CONFIG_MTD_SPLIT_*` and `mount_root` suppressed.
- **Passive Kernel Register Inspector (`/proc/rsd0614_hw_survey`, `0444`, `.write = NULL`)**: zero-write KSEG1 snapshot of `SYSC` (`SOC_ID`, decoded `BOOTSTRAP`, `BOND_OPTION`, `CLKMANAGE`, `ENABLE_IP`, `WLAN_CLK`, `MDIORST`), `MEMC` (`DMR`, `DCR`), `PIN_MUX_SEL0..18` + `RGMII_PAD_CTRL` (`0xB8000850`), `GICR`, `GPIO` `PABCD`/`PEFGH`, and `CLKMANAGE BIT(11)`-guarded `CPU_IFACE` + `SWCORE` (`PITCR`, `PCRP0..8`, `PSRP0..8`, `P0GMIICR`, `EXTPCR0`, and per-port MIB RX/TX counters).
- **Opt-In Post-Survey One-Shot Probes (`/proc/rsd0614_probe`, `0600`, never run at boot)**:
  - `smi`: pinmux-guarded (`PIN_MUX_SEL2[11:4]==0x66`, `PABCD_CNR[19:18]==0`) 2-wire SMI read on `PABCD` bits `18`/`19` ONLY (never touching `PEFGH` or reset `0x1322`), unlocking `0x13C2=0x0249` and reading `RTL8367` `chip_num`/`chip_ver`/`chip_mode`, `extif`/RGMII, `pbmp`, and per-port link status before restoring `PABCD` bits `18..19`.
  - `wmac`: keeps `GIMR BIT(29)` masked, gates `SR+0x64 |= 0x1f`, reads `0xB8640000` (`+0x000..+0x100`, `cut`, `HAL type`), and restores `SR+0x64`.
  - `pcie0`: keeps `GIMR BIT(21)` masked, runs donor 40 MHz RC0 reset + `SR+0x100` + `SR+0x50 BIT(1)` PERST#, polls `0xB8B00728` for `LTSSM == 0x11`, and reads `0xB8B10000` (`10ec:b814` `RTL8814BR`) **only** when `LTSSM == 0x11`.
- **Sanitized Userspace Collector (`/usr/sbin/rsd0614-survey`)**: manual `passive`, `buttons [seconds]`, `probe-smi`, `probe-wmac`, `probe-pcie0`, `probe-all`, and `backup-guide` commands; reads structural headers from `/dev/mtd0ro` and `/dev/mtd2ro` ONLY while strictly redacting `mtd1` (`cfg`), `mtd3` (`cpe`), `mtd4` (`cfm`), and `mtd5` (`cfm_backup`).

## Consolidated Roadmap (M1 -> M2 -> M3)

1. **M1 (`v5.4.1` — this build)**: Run `rsd0614-survey passive`, `rsd0614-survey buttons 10`, and `rsd0614-survey probe-all` on physical RSD0614 V1.0 over UART (`AUTOBURN 0` RAM boot).
2. **M2 (Functional RAM-boot router)**: Enable verified `&ethernet` (`rtl819x-eth` + `RTL8367RB` VLANs), verified GPIO buttons/LEDs, `&pcie0` 40 MHz bus enumeration, and 2.4 GHz `rtl8192cd` WMAC AP (with runtime read-only calibration from `/dev/mtd1ro`) in a single RAM-boot build.
3. **M3 (`RTL8814BR` `10ec:b814` 5 GHz driver)**: Port/integrate `RTL8814B` (`10ec:b814`) driver support (absent from both pinned `ggbruno` `rtw88` and `ADCDS` `rtl8192cd` v3.4.11e).

## Verification boundary

- v5.3.9 serial-only RAM-boot & interactive `ttyS0` shell on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.4.0 CI compile & 25/25 offline policy audit (`run 45036891876`): **PASS (COMPILE/AUDIT ONLY; HARDWARE RUNTIME NOT VERIFIED)**.
- v5.4.1 omnibus read-only qualification on physical RSD0614 V1.0 UART/runtime: **NOT YET VERIFIED**.
- Disabled board peripherals (`ethernet` / `RTL8367RB`, `pcie0` / `RTL8814BR`, `wmac`, LEDs/buttons): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
