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

- **v5.6.1 (`v5.6.1-m3-wifi-pcie-hardened-ramboot`) hardware run on physical Rock Space RSD0614 V1.0** (CI run `#45434537894`, `4,183,280` bytes / `0x003FD4F0`, SHA-256 `5a7d31aa451fd386e1063a5fe0f73ba218359f9fd5c3e02e4e739cee2a7a5b35`):
  - **Verified PASS on hardware**:
    - `PCIe0` trained cleanly on **attempt 1/3** (`LTSSM(0x728)=0x039b4f11 clk=40000000Hz link_up=1 (attempt 1/3)`, `10ec:b814` `RTL8814BR` enabled).
    - `rtl8192cd.ko` loaded cleanly with **zero unresolved symbols**, read-only `/dev/mtd1` (`65536B` Tenda KV factory calibration) parsed cleanly (`rfe_type=1`, `mac_from_nvmem=1`), and both `wlan0` (`0000:01:00.0` `RTL8814BR` 5 GHz) and `wlan1` (`18640000.wmac` `RTL8197G` 2.4 GHz, `HAL 0x15`) registered with `32.4 MiB` free RAM (`MemFree=32436 kB`).
    - Wired DHCP (`192.168.1.106` via `dnsmasq-dhcp`), `ping 192.168.1.1`, `uhttpd` (`0.0.0.0:80`), and `dropbear` (`0.0.0.0:22`) active.
  - **Three runtime blockers isolated from serial log & Windows test**:
    1. **LuCI `http://192.168.1.1` (`luci.js`) & `ssh root@192.168.1.1` (`SSH2_MSG_KEXINIT`) hang**: on the RGMII trunk (`SoC Port 0 <-> RTL8367S Port 6`), full `1500B` MTU TCP segments carry **both** the 4B `0x8899` Realtek CPU tag and the 4B `802.1Q` VLAN tag (`14 + 4 + 4 + 1500 + 4 = 1526` bytes), exceeding the `RTL8367S` (`0x6367`) `CFG0` (`0x088c`) power-on default of `0x05f2` (`1522` bytes), silently dropping all full-MTU TCP segments while passing small packets (`ping`, `index.html`). In addition, `_New_swNic_send` cleared `CPUICR` bit 29 (`BUSBURST_128WORDS`) on every TX doorbell (`0xE4000000 -> 0xC4000000`).
    2. **Missing `RSD0614-OpenWrt-5G` & `RSD0614-OpenWrt-2G` SSIDs (`wlan0`/`wlan1` left `DOWN`)**: `8192cd_cfg.h` disabled `_INCLUDE_PROC_FS_` under `CONFIG_RTL8192CD_LINUX6_BUS`, so `/proc/wlan0` & `/proc/wlan1` were absent and `/lib/netifd/wireless/rtl8192cd.sh`'s `[ -e "/proc/$phy_ifname/mib_all" ]` check aborted with `NO_DEVICE` before writing `/tmp/Wireless/RTL8192CD.dat` or running `ifconfig wlan0/wlan1 up`; `SIOCGIWNAME` (`rtl_iwhandler[1]`) was also `NULL` (`iwconfig`: `no wireless extensions`).
    3. **False `PRESSURE` spam (`USEDDSC=345`) & false 5s `RX-STALL WEDGE` reset**: with 3 unplugged LAN ports (`MaxDSC=90` per port), normal idle `USEDDSC` is `345` (`< SBFCR1 FCOFF=400`, `< SBFCR0 RUNOUT=480`), tripping the hardcoded `used > 256` check.

## v5.6.2 scope — Consolidated Full-MTU Wired Gigabit + Dual-Band Wi-Fi AP + LuCI 19.07 RAM-Boot (`v5.6.2-m3-wifi-mtu-hardened-ramboot`)

Consolidates all fixes for the `v5.6.1` physical hardware findings plus preventive LuCI/low-memory/TX-reclaim guards into one single RAM-boot build:
- **`RTL8367S` `1552B` trunk max-frame & SoC NIC TX/threshold hardening (`patches/9996-rsd0614-vg-rgmii-and-pcie.patch`)**:
  - Adds `rtl8367s_set_max_len_1552()` programming `0x1200` bits `[14:13]=0x6000`, `0x0884` bits `[1:0]=0x0003`, and `0x088c`/`0x088d` = `0x0610` (`1552B >= 1526B`) in **both** `rtl8367s_cpu_tag_enable()` and `rtl8367b_setup()` (preventing `swconfig dev switch0 set apply 1` from clobbering `0x1200` back to `0x2000`).
  - Removes `REG32(CPUICR) & ~(1u << 29)` from `_New_swNic_send` so `BUSBURST_128WORDS` stays latched across TX doorbells, linearizes nonlinear SKBs (`skb_linearize`) before single-descriptor `dma_map_single` in `rtl819x_eth_xmit`, programs `MACCR` `CF_FCDSC=0x48` on VG (`0x804a1485`), and raises `USEDDSC` pressure/stall threshold from `256` to `400`.
- **Dual-band Wi-Fi procfs, `netifd`, WEXT & `RTL8814B` TX reclaim (`patches/rtl8192cd-4.14-rsd0614.patch`, `harden_source.py`)**:
  - Enables `_INCLUDE_PROC_FS_` on Linux `< 5.0.0` (`/proc/wlan0` & `/proc/wlan1` live) **and** switches `lib/netifd/wireless/rtl8192cd.sh` device checks from `/proc/.../mib_all` to `/sys/class/net/...` so AP bring-up (`RTL8192CD.dat` + `ifconfig wlan0/wlan1 up` + `br-lan` bridge attach) never depends on procfs.
  - Adds `SET_NETDEV_DEV(dev, priv->pshare->linux_dev)` before `register_netdev()`, wires AP-safe `rtl_giwname` (`SIOCGIWNAME`) so `iwconfig`/`libiwinfo` recognize `wlan0`/`wlan1`, frees `mibstr`/`cmd_buf` on `valstr` `kmalloc` failure, and extends `UpdateSWTXBDHostIdx88XX` TX-reclaim `tx_tasklet` kicks to `IS_HARDWARE_TYPE_8814B` (`HCI_TX_DMA_QUEUE_HI0_V2`).
- **LuCI 19.07 `wireless.js`, 64 MiB lowmem sysctl & `rsd0614-survey net|diag` (`build-rsd0614-initramfs.sh`, `harden_source.py`)**:
  - Extends `CBIWifiFrequencyValue` in `wireless.js` to populate `rtl8192cd` `n`/`ac` modes, `HT20`/`HT40`/`VHT20`/`VHT40`/`VHT80` widths, and fallback 2.4/5 GHz channel lists while guarding `write()` against empty values.
  - Adds `/etc/sysctl.d/31-rsd0614-lowmem.conf` (`vm.min_free_kbytes=2048`) to prevent `GFP_ATOMIC` reserve exhaustion on 64 MiB DDR2 when both radios open, and adds `rsd0614-survey net` and `rsd0614-survey diag`.
- **Unchanged safety boundary**: all 6 MTD partitions stay `read-only`, `pcie1` stays disabled, unverified LED GPIOs stay unclaimed, and persistent flash remains **NO-GO**.

## Verification boundary

- v5.3.9..v5.6.1 `ttyS0`, `spi0` `BH25Q64` read-only MTDs, `GPIO1_4` Reset button, `RTL8367S` (`smi_pefgh_24_23`, 1000M/FD, VLAN 1/2), `RTL8197FH-VG` 6-dword `eth0` (`newdesc=1`, DHCP, `ping`), `PCIe0` first-attempt link-up (`LTSSM=0x039b4f11`, `10ec:b814`), and `rtl8192cd.ko` dual-radio probe + read-only `/dev/mtd1` factory calibration on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.6.2 CI OpenWrt compile, ELF `__ksymtab` / `proc_init` / `giwname` audit & `deep_audit.py`: **PASS** (CI run `#45520998735`, `6m25s`, `4,220,464` bytes / `0x00406630`, `decoded_size=14,611,097` bytes / `13.93 MiB`, SHA-256 `6cdc86de0a0d346cd7cb6fedf4408237060b823d0bb20d9969de0442c25f88b3`, `32/32` offline policy checks PASS, `rtl8192cd.ko` `undef=157 missing=0 proc_init=1 giwname=1 bss=689152B`).
- v5.6.2 full-MTU LuCI/SSH over `RTL8367S` (`maxLen088c=0610`) and live `RSD0614-OpenWrt-5G` / `RSD0614-OpenWrt-2G` AP broadcast on physical RSD0614 V1.0: **NOT YET VERIFIED FOR v5.6.2**.
- Disabled board peripherals (`pcie1`, LEDs): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
