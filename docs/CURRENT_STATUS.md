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

## v5.6.0 scope — Consolidated M3 Dual-Band Wi-Fi + LuCI 19.07 + Wired Gigabit RAM-Boot (`v5.6.0-m3-dualband-wifi-luci-ramboot`)

Consolidates all remaining RAM-boot router capabilities on top of the 100% hardware-verified `v5.5.1` M2 wired Gigabit stack (`9996-rsd0614-vg-rgmii-and-pcie.patch` untouched):
- **Dual-band Wi-Fi (`kmod-rtl8192cd-rsd0614`)**: out-of-tree pinned Realtek SDK v3.6.0 driver (`tobyw121/Openwrt_RTL` @ `1529557b0936019462c4b24f98bc8436d359bd3a`) patched cleanly for Linux 4.14.187 / GCC 8.4.0 (`patches/rtl8192cd-4.14-rsd0614.patch`) driving BOTH:
  - **`wlan0` (5 GHz, 4x4 802.11ac `VHT80` ch 36)**: PCIe0 `RTL8814BR` (`10ec:b814`, IRQ 5, `GIMR BIT(21)`),
  - **`wlan1` (2.4 GHz, 2x2 802.11n `HT20` ch 6)**: on-SoC `RTL8197G` (`HAL 0x15`, `0x18640000 0x40000`, IRQ 6, `GIMR BIT(29)` armed on WMAC probe and included in `mips_chip_irqs`).
- **WEXT + in-kernel WPA2-PSK + read-only runtime calibration**: uses `CONFIG_MW5_LEGACY_WEXT=y` + `INCLUDE_WPA_PSK` + `/etc/Wireless/RTL8192CD.dat -> /tmp/Wireless` (no `cfg80211`/`wpad`/`hostapd` overhead), runtime read-only `get_mtd_device_nm("cfg")` + `mtd_read()` `tenda-kv` RF calibration/MAC loading with safe eFuse fallback, and an atomic `lock`-protected dual-band `netifd` handler (`/lib/netifd/wireless/rtl8192cd.sh`, zero LED GPIO claims).
- **OpenWrt 19.07 LuCI Web GUI (`http://192.168.1.1`)**: pinned EOL Lua-era `openwrt/luci` (`f25285a6c26e8776f153994704710cb8e51fad91`) and `openwrt/packages` (`6df6880800397ab3821572c6c5ad18e300374d9e`) feeds (`uhttpd`, `uhttpd-mod-ubus`, `luci`, `luci-base`, `luci-mod-admin-full`, `luci-theme-bootstrap`, `luci-app-firewall`, `luci-proto-ppp`, `cgi-io`).
- **On-device diagnostics & benchmarking**: `wireless-tools` (`iwpriv`, `iwconfig`, `iwlist`), `ethtool`, `iperf3`, and read-only `rsd0614-survey wifi`.
- **Unchanged safety boundary**: all 6 MTD partitions stay `read-only`, `pcie1` stays disabled, unverified LED GPIOs stay unclaimed, and persistent flash remains **NO-GO**.

## Verification boundary

- v5.3.9..v5.5.1 `ttyS0`, `spi0` `BH25Q64` read-only MTDs, `GPIO1_4` Reset button, `RTL8367S` (`smi_pefgh_24_23`, 1000M/FD, VLAN 1/2), `RTL8197FH-VG` 6-dword `eth0` wired Gigabit (`ping 192.168.1.1` 1ms 0% loss, Dropbear SSH), `RTL8197G` WMAC (`HAL 0x15`), and `PCIe0` (`10ec:b814` BAR0/BAR2 assigned) on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.6.0 CI OpenWrt compile & `deep_audit.py`: **PENDING M3 BUILD**.
- v5.6.0 dual-band Wi-Fi (`wlan0` 5 GHz + `wlan1` 2.4 GHz) & LuCI web GUI on physical RSD0614 V1.0: **NOT YET VERIFIED FOR v5.6.0**.
- Disabled board peripherals (`pcie1`, LEDs): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
