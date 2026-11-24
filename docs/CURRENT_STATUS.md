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

## v5.5.0 scope — M2 Consolidated Wired Gigabit + PCIe0 RAM-Boot (`v5.5.0-wired-pcie-ramboot`)

Every verified wired/bus peripheral is consolidated into a single RAM-boot image:
- **External `RTL8367S` 5-port Gigabit switch + `rtl819x` SoC MAC (`9996-rsd0614-vg-rgmii-and-pcie.patch`)**:
  - `rtl8367b` enabled on exact verified SMI pins (`gpio-sck = <&gpio1 24 GPIO_ACTIVE_HIGH>`, `gpio-sda = <&gpio1 23 GPIO_ACTIVE_HIGH>`, `cpu_port = <6>`) without disturbing `PH2` (`gpio1 26` hardware `RESET#`);
  - `RTL8197FH-VG` (`0x81970000`) RGMII fixes: preserves VG `0xB8000850` (`PAD_P0_RGMII_MODE` bit 25 / `0x579fff7f`), sets `EXTPCR0[19:16]=8` + `PITCR[17:12]=1` (`CF_FIX_IPG`), defaults `P0GMIICR` to verified `TX_delay=1, RX_delay=7` (tunable via `p0_rx_delay`/`p0_tx_delay`), and defaults `fabric_gw_rearm=0` on `rockspace,rsd0614`;
  - Standard OpenWrt L2 + Linux software routing/NAT/DHCP/SSH: `switch0` VLAN 1 (`4 6t`, WAN `eth0.1` DHCP, MAC `02:06:14:00:00:02`) and VLAN 2 (`0 1 2 3 6t`, LAN `br-lan` `eth0.2` `192.168.1.1/24`, MAC `02:06:14:00:00:01`), `hwnat=0`, `fabric_gw_rearm=0`, `swconfig dev switch0 set apply 1` via `etc/init.d/rsd0614-net` (`START=97`, no `USE_PROCD`).
- **Physical Reset button**: `gpio-keys-polled` `reset` (`KEY_RESTART`) on verified `<&gpio1 4 GPIO_ACTIVE_LOW>`.
- **40 MHz `PCIe0` bus**: `&pcie_clk` set to `40000000`, `&pcie0` enabled with Realtek SDK v3.6.0 VG MDIO tuning (`0x08=0x3101`), and `GIMR BIT(21)` unmasked for `10ec:b814` (`RTL8814BR`) PCI enumeration.
- **Why Wi-Fi moves cleanly to M3**: `v5.4.2` silicon probe proved BOTH radios require Realtek SDK v3.6.0 HALs — on-SoC 2.4 GHz WMAC is **`RTL8197G` (`HAL 0x15`)** (not `RTL8197F` `0x0E` from donor SDK v3.4.11e) and PCIe0 5 GHz is **`RTL8814BR` (`10ec:b814`, `HAL 0x11`)**. Keeping `&wmac` disabled and `BIT(29)` masked in `v5.5.0` delivers a rock-solid wired Gigabit + PCIe0 milestone first.

## Consolidated Roadmap (M2 -> M3)

1. **M2 (`v5.5.0-wired-pcie-ramboot` — this build, hardware runtime `NOT YET VERIFIED`)**: Verify full Gigabit wired router (`LAN` `192.168.1.1` DHCP/SSH, `WAN` DHCP/NAT, `swconfig dev switch0 show`), `Reset` button event, and `PCIe0` `10ec:b814` enumeration in RAM.
2. **M3 (Dual-band Wi-Fi — `RTL8197G` `HAL 0x15` 2.4 GHz + `RTL8814BR` `10ec:b814` 5 GHz)**: Integrate Realtek SDK v3.6.0 `rtl8192cd` driver/HAL supporting both `HAL_HW_TYPE_ID_8197G` (`0x15`) and `HAL_HW_TYPE_ID_8814B` (`0x11`) with runtime read-only `/dev/mtd1ro` calibration in RAM. Persistent flash remains **NO-GO** unless an explicit later milestone changes `AGENTS.md`.

## Verification boundary

- v5.3.9, v5.4.1 & v5.4.2 `ttyS0` shell, `spi0` `BH25Q64` read-only MTDs, passive `SYSC`/`PINMUX`/`GPIO`/`SWCORE` register survey, `GPIO1_4` button, `RTL8367S` (`smi_pefgh_24_23`), `RTL8197G` WMAC (`HAL 0x15`), and `PCIe0` `10ec:b814` Link UP on physical RSD0614 V1.0: **PASS (VERIFIED)**.
- v5.5.0 CI OpenWrt compile & `deep_audit.py`: **NOT YET VERIFIED**.
- v5.5.0 wired Gigabit (`eth0.2`/`eth0.1`/`switch0`), Reset button, and `PCIe0` Linux driver runtime on physical RSD0614 V1.0: **NOT YET VERIFIED**.
- Disabled board peripherals (`pcie1`, `wmac` `RTL8197G`, LEDs): **NOT YET VERIFIED**.
- Persistent flash: **NO-GO**.
