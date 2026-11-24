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
  - Package & mux/GPIO truth: `SYSC_BOND_OPTION=0x00000004` (`BSP_BOND_97FN`), `PINMUX_SEL2=0x00000000`, `PINMUX_SEL13=0x33320000`, `PINMUX_SEL14=0x20000000` (`PH2` = `RTL8367S` reset held high in `GPIO_PEFGH_DAT=0x05c00013`), `PINMUX_SEL17=0x10110110`.
  - Physical Reset button verified on **`GPIO_PEFGH` bit 4 (`&gpio1 4 GPIO_ACTIVE_LOW`, `BSP_GPIO_PIN_E4`, `xor=0x00000010`)**.
  - RGMII trunk on `SWCORE` Port 0 verified: `SWCORE_PITCR=0x00000001`, `SWCORE_P0GMIICR=0x00037d57` (`TX_delay=1`, **`RX_delay=7`**, CPU-tag bits off), `SWCORE_PCRP0=0x16972039` (`ExtPHYID=22`, `Pause=3`, `Force 1000M/FD`), `SWCORE_EXTPCR0=0x000c0000`, `PINMUX_RGMII_PAD_CTRL=0x579fff7f`, `SWCORE_PSRP0=0x0000307a`, `MIB_P0 <-> MIB_P6` = `5,731` frames (`0x318dd9` bytes, zero loss).
- **v5.4.2 (`v5.4.2-omnibus-readonly-survey`) `rsd0614-survey probe-all` 100% PASS on physical Rock Space RSD0614 V1.0** (CI run `#45087657332`, `2,934,544` bytes / `0x2CC710`, SHA-256 `ba761d13f34b492f220c599ec16e2747344f9169e0481edccba56214c73bbef2`):
  - **`smi`**: `SMI_STATUS=ok`, **`SMI_BUS=smi_pefgh_24_23`** (**`SCK=&gpio1 24` (`PH0`), `SDA=&gpio1 23` (`PG7`)**), `SMI_CHIP_NUM=0x6367`, `SMI_CHIP_VER=0x0020`, `SMI_CHIP_MODE=0x0020` (**`RTL8367S`**!), `SMI_DIS_1305=0x0010` (`EXT1` RGMII), `SMI_EXT1_RGMXF_1307=0x0002`, `SMI_DI_FORCE1_1311=0x1076`, `SMI_EXTIF_1D11=0x1500`, `SMI_CPU_MASK_1219=0x0040` (`cpu_port=6`), `SMI_CPU_CTRL_121A=0x00b5`, `SMI_PBMP_P0..P3=0x00ef` (LAN `0..3`), `SMI_PBMP_P4=0x00f0` (WAN `4`), `SMI_PORT_STATUS_P2=0x09f6` & `P6=0x0076` (1000M/FD Link UP).
  - **`wmac`**: `WMAC_STATUS=ok`, `SR64: 0x0->0x1f->0x0`, `BOND_STRAP=4` (`97FN`), `REG_000=0x51c0b2f3`, `REG_0F0=0x0c591139` (`CUT_VER=1`), **`REG_0FC=0x00000015` (`WMAC_HAL_TYPE_ID=21` = `HAL_HW_TYPE_ID_8197G`)**, `REG_100=0xeaeaeaea`.
  - **`pcie0`**: `PCIE0_STATUS=link_up`, `XTAL_MHZ=40`, `LTSSM=0x030e9d11` (`L0`), `RC_ID=0x819710ec`, **`EP_ID=0xb81410ec` (`10ec:b814` = `RTL8814BR`)**, `EP_CLASS=0x02800000`, `EP_SUBSYS=0xb81410ec`.

- **v5.5.0 (`v5.5.0-wired-pcie-ramboot`) hardware run on physical Rock Space RSD0614 V1.0** (CI run `#45364422799`, `2,959,120` bytes / `0x002D2710`, SHA-256 `b9795cc5bb5d400f2c88e38c3b99749103834fb12699bdd2a663ac5f0dfe36be`):
  - **`PCIe0` (`10ec:b814` `RTL8814BR`) Linux PCI subsystem**: **PASS** (`LTSSM=0x03d78a11`, `clk=40000000Hz`, `link_up=1`, `0000:00:00.0 10ec:8197`, `0000:01:00.0 10ec:b814 class=0x028000`, BAR0 `io 0x18c00000` & BAR2 `mem 0x19000000-0x1900ffff 64bit`).
  - **`RTL8367S` Gigabit switch (`gpio1 24/23` -> GPIOs 472/471) & RGMII trunk**: **PASS** (`RTL8367S chip found`, Port 2 & Port 6 `1000baseT full-duplex`, `VLAN 1: 4 6t`, `VLAN 2: 0 1 2 3 6t`, `5,781` packets, `0` FCS errors; `PITCR=00001001`, `P0GMIICR=060f7d57`, `PCRP0=16942039`, `EXTPCR0=00080000`, `PAD=579fff7f`; `USEDDSC` rose from `18` to `100` under LAN traffic).
  - **Root cause isolated for `eth0` `rx_pkts=0` + `CPUIISR=00020000` runout storm**: bootloader printed `use Switch new descriptor` and left `CPUICR1=0x00186183` (`CF_RXDESC=6`, `CF_TXDESC=6`, `CF_PKT_HDR_TYPE=1` `TX_PKTHDR_SHORTCUT_LSO` single-level 6-dword/24-byte descriptor mode), while donor `rtl819x_swnic.c` only drove legacy 2-level (`rtl_pktHdr` + `rtl_mBuf`) 4-byte pointer rings without resetting `CPUICR1` or supporting 6-dword descriptors.

- **v5.5.1 (`v5.5.1-vg-newdesc-ramboot`) M2 wired Gigabit 100% VERIFIED on physical Rock Space RSD0614 V1.0** (CI run `#45379106697`, `2,960,336` bytes / `0x002D2BD0`, SHA-256 `7bde54541c710954f59e7549f0b130ae46030a8de7b9cc779352a8e31280df65`):
  - Native `RTL8197FH-VG` 6-dword new-descriptor `eth0` engine booted cleanly (`newdesc=1`, `CPUICR1=0x001861d3`, `rx_pkts=107`, `runout=0`, `CPUIISR=00000000`, `FCS wedge detector armed`, zero errors/oops).
  - Full LAN connectivity verified from Windows PC: `ping 192.168.1.1` = `4/4` replies (`1 ms`, `0%` loss) and `ssh root@192.168.1.1` reached Dropbear cleanly.

- **v5.6.0 (`v5.6.0-m3-dualband-wifi-luci-ramboot`) hardware run on physical Rock Space RSD0614 V1.0** (CI run `#45399545588`, `4,179,472` bytes / `0x003FC610`, SHA-256 `931259c4f1e88e6b5084844133d5067e9440fe4f417bf23eb006a313e0829d22`):
  - **Verified PASS on hardware**: wired Gigabit `eth0` (`newdesc=1`, `rx_pkts=649`, `runout=0`, `CPUIISR=00000000`, `FCS wedge detector armed`), `RTL8367S`, `BH25Q64` 6 read-only MTDs, LuCI/`uhttpd` + `40.9 MiB` free RAM (`MemTotal=59460 kB`, `MemFree=40936 kB`), and `netifd` wireless UCI parsing for `radio0`/`radio1`.
  - **Two runtime blockers isolated from serial log**:
    1. `rtl8192cd: Unknown symbol sk_pacing_shift_update (err 0)` prevented `rtl8192cd.ko` from loading (`sk_pacing_shift_update` is absent in Linux 4.14.187; unguarded `>= KERNEL_VERSION(4,4,140)` enabled it while `-Wno-implicit-function-declaration` hid the call).
    2. `PCIe RC0 link check: LTSSM(0x728)=0x0c454504 clk=40000000Hz link_up=0` intermittently stalled in `S_POLL_CONFIG` (`0x04`) due to unsynchronized `PWRCR`/`PERST#` timing without retry.

## v5.6.1 scope — Hardened M3 Dual-Band Wi-Fi + PCIe0 + LuCI 19.07 + Wired Gigabit RAM-Boot (`v5.6.1-m3-wifi-pcie-hardened-ramboot`)

Consolidates all fixes for the `v5.6.0` boot log findings AND every latent runtime defect caught by full-stack audit into one hardened RAM-boot build:
- **Driver symbol & fail-closed ELF audit (`patches/rtl8192cd-4.14-rsd0614.patch`, `export_build_evidence.py`, `deep_audit.py`)**: guards `sk_pacing_shift_update` to `4.4.140..4.4.x` / `>= 4.16.0` (0 unresolved symbols vs `vmlinux` `__ksymtab_*`) and enforces pure-Python ELF32-LE MIPS `SHN_UNDEF` vs `System.map` `__ksymtab_*` + `.modinfo` GPL + `.bss <= 1.5 MiB` checks on every build.
- **64 MiB RAM safety (`CONFIG_RTL_SHRINK_MEMORY_SIZE=y`)**: bounds `NUM_TX_DESC=256`, `NUM_RX_DESC=256`, `NUM_RX_DESC_2G=256`, `MAX_RX_BUF_LEN=2600`, `NUM_STAT=16`, `RTL8192CD_NUM_VWLAN=1` so coherent DMA stays below order-7 and RX SKBs fit single 4 KiB pages (eliminating the order-10 `GFP_ATOMIC` / ~55.6 MiB OOM failure).
- **Dual-radio DMA, IRQ & calibration hardening**: enables coherent TXBD/TXDESC/beacon DMA for `RTL8814BR` (`VERSION_8814B`) + fixes MIPS32 `>> 32` UB (`lower_32_bits`/`upper_32_bits`), fixes `Hal88XXGen.c` `InterruptMaskExt` typo, moves `RTL8197G` `GIMR BIT(29)` unmask from probe to post-`request_irq()` in `rtl8192cd_open()` (with mask before `free_irq()`), adds `0xB8000064` readback fence + `mdelay(1)`, supports colon-formatted factory MACs with non-fatal fallback in `rtl8192cd_board.c`, includes `VERSION_8814B` in NAPI TX reclaim, guards the watchdog reset trap, and eliminates the 20-byte `mibstr` overflow in `8192cd_comapi.c`.
- **PCIe0 link reliability & quiet console (`patches/9996-rsd0614-vg-rgmii-and-pcie.patch`)**: synchronizes `PWRCR=0x01` + `PERST#=0` (`290 ms`) -> `PWRCR=0x81` (`10 ms`) -> `PERST#=1` with readback fences and a 3-attempt bounded retry loop (gating off `CLKMANAGE BIT(14)` if all 3 attempts fail); silences steady-state `rtl819x DP: poll#` / `isr#` UART spam via `dp_heartbeat=0` while preserving boot bring-up and unconditional `PRESSURE` warnings.
- **Userspace & LuCI 19.07 Wi-Fi fixes**: corrects `rtl8192cd.sh` `2ndchoffset` (`HT40+=2`, `HT40-=1`), fixes `psk-mixed` `encmode=4` (never `6`) + cipher parsing + explicit MIB defaults + `lock`-scoped `/etc/Wireless` + empty/duplicate VIF guards, expands `rsd0614-survey wifi` with PCI/LuCI/sanitized config inspection, and patches LuCI `wireless.js` with `rtl8192cd` WPA2/PSK encryption options.
- **Unchanged safety boundary**: all 6 MTD partitions stay `read-only`, `pcie1` stays disabled, unverified LED GPIOs stay unclaimed, and persistent flash remains **NO-GO**.

## Verification boundary

- v5.3.9..v5.6.0 `ttyS0`, `spi0` `BH25Q64` read-only MTDs, `GPIO1_4` Reset button, `RTL8367S` (`smi_pefgh_24_23`, 1000M/FD, VLAN 1/2), `RTL8197FH-VG` 6-dword `eth0` wired Gigabit (`ping 192.168.1.1` 1ms 0% loss, Dropbear SSH, `rx_pkts=649`, `runout=0`), `RTL8197G` WMAC (`HAL 0x15`), `PCIe0` (`10ec:b814`), and LuCI/`uhttpd` + 40.9 MiB free RAM on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.6.1 CI OpenWrt compile, ELF `__ksymtab` symbol check & `deep_audit.py`: **PENDING CI RUN**.
- v5.6.1 dual-band Wi-Fi (`wlan0` 5 GHz + `wlan1` 2.4 GHz), hardened PCIe0 retry, and LuCI Wi-Fi config on physical RSD0614 V1.0: **NOT YET VERIFIED FOR v5.6.1**.
- Disabled board peripherals (`pcie1`, LEDs): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
