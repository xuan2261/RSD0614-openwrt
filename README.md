# Rock Space RSD0614 OpenWrt bring-up

Experimental, evidence-driven OpenWrt/Linux bring-up for **Rock Space RSD0614 V1.0** on the Realtek RTL8197F family (`RTL8197FH-VG`).

## Current milestone

The project has already verified on a physical RSD0614 unit:

- 64 MiB DDR2 RAM;
- BH25Q64 8 MiB SPI NOR;
- UART `115200 8N1` and RealTek bootloader command mode;
- TFTP RAM load at `0x81000000` with `AUTOBURN 0`;
- OpenWrt 4.14.187 RAM-boot reaches Linux kernel init and `procd` userspace (`keep_bootcon`);
- v5.3.7 bounded UART IRQ diagnostics isolated silent `ttyS0` TX and the RX-timeout storm (`timeout=441/512`, `lsr=61`, `rbr=00`, `lcr=13`) to `0004-rtl8197f-dw-uart.patch` forcing non-VG `+0x24`/`adjlcr` quirks onto **RTL8197FH-VG** (`0x81970001`, standard `+0x00` 16550/DW-APB);
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`), v5.4.1 & v5.4.2 (`v5.4.2-omnibus-readonly-survey`) hardware-verified on physical RSD0614 V1.0**:
  - Clean `ttyS0` 16550A TX/RX console without `keep_bootcon` (`soc_id=0x81970001 mode=vg-std`, `BOOTSTRAP=0x41258ee0` 40 MHz XTAL / 1000 MHz CPU / 64 MiB DDR2-533, `BOND_OPTION=0x4` `97FN`, `irq17=105, ERR=0`);
  - Read-only `spi0` / `BH25Q64` (`0x684017`, `div 28`, 8 MiB) across all 6 `read-only` MTD partitions (`mtd0..mtd5`, `flags=0x800`), stock `mtd2ro` `cr6c` header (`start=0x80a00000`, `burn=0x30000`, `len=0x256c02`);
  - Physical Reset button verified on **`GPIO_PEFGH` bit 4 (`&gpio1 4 GPIO_ACTIVE_LOW`, `BSP_GPIO_PIN_E4`, `xor=0x10`)**;
  - External switch verified as **`RTL8367S` (`chip_num=0x6367`, `ver=0x0020`, `EXT1=cpu_port 6`, LAN `0..3=0x00ef`, WAN `4=0x00f0`)** over bit-banged SMI **`SCK=&gpio1 24` (`PH0`), `SDA=&gpio1 23` (`PG7`)**, paired with live `SWCORE` Port 0 RGMII trunk (`P0GMIICR=0x00037d57` RX delay `7`, `RGMII_PAD_CTRL=0x579fff7f`, `EXTPCR0=0x000c0000`);
  - On-SoC 2.4 GHz WMAC verified alive as **`RTL8197G` (`HAL_HW_TYPE_ID=0x15`, `cut=1`)**;
- **v5.5.0 & v5.5.1 (`v5.5.1-vg-newdesc-ramboot`, CI run `#45379106697`) M2 wired Gigabit hardware-verified 100% on physical RSD0614 V1.0**:
  - `PCIe0` (`10ec:b814` `RTL8814BR`, 40 MHz, BAR0/BAR2 assigned), `RTL8367S` (`1000M/FD`, `VLAN 1: 4 6t`, `VLAN 2: 0 1 2 3 6t`), and `RTL8197FH-VG` native 6-dword new-descriptor `eth0` (`newdesc=1`, `CPUICR1=0x001861d3`, `rx_pkts=107`, `runout=0`, `CPUIISR=00000000`, `FCS wedge detector armed`);
  - `ping 192.168.1.1` (`4/4` replies, `1 ms`, `0%` loss) and Dropbear `ssh root@192.168.1.1` reached cleanly with zero kernel oops or errors;
- **v5.6.3 (`v5.6.3-m3-wifi-bringup-fixed-ramboot`, CI run `#45610643244`) dual-band Wi-Fi AP + full-MTU LuCI/SSH verified on physical RSD0614 V1.0**:
  - Zero kernel panic; `PCIe0` trained cleanly on **attempt 1/3** (`LTSSM=0x03983311`, `10ec:b814`), `RTL8367S` `1552B` trunk max-frame (`reg1200=7fcb maxLen088c=0610`) persisted across `swconfig`, full-MTU LuCI web login + Dropbear SSH login succeeded cleanly (`dropbear` deferred to `START=98`);
  - Both 5 GHz **`RTL8814BR` (`wlan0`, ch 36 VHT80, `RSD0614-OpenWrt-5G`)** and 2.4 GHz **`RTL8197G` (`wlan1`, ch 6 HT20, `RSD0614-OpenWrt-2G`)** APs came UP and joined `br-lan` with read-only `/dev/mtd1` factory RF calibration (`tgpwr=17/19 dBm`), and a real smartphone associated on 5 GHz WPA2-PSK at **`VHT NSS2-MCS9` (`780 Mbps`)**, `tx_fail=0`, 4-chain RSSI `79`, DHCP lease `192.168.1.179`, with **`26.5 MiB` free RAM**;
- **v5.6.4 (`v5.6.4-m3-router-hardened-ramboot`, CI run `#45723595834`) verified on physical RSD0614 V1.0**:
  - Zero panic, zero UART `n=512` RX byte-stealing, zero `swnic`/`8367S` boot spam, `27.4 MiB` free RAM;
  - Stale `switch0` `VLAN 3..8` / `VLAN 7` WAN->LAN L2 bypass 100% closed (only `VLAN 1 [4 6t]` & `VLAN 2 [0 1 2 3 6t]`), `FLOWOFFLOAD` active in `iptables FORWARD`, `block_relay=0` on both radios with PC LAN -> 5 GHz phone `ping 192.168.1.179` (`4/4`, `0%` loss, avg `7 ms`), WEXT freq/rate/txpow/operstate UP (`5.18 GHz` `1.56 Gb/s` `17 dBm` & `2.437 GHz` `130 Mb/s` `19 dBm`), and LuCI login via `uhttpd-mod-lua`;
- **v5.6.5 (`v5.6.5-m3-final-ramboot`, CI run `#45827182660`)**: compiled & offline-audited (`32/32` PASS, `4,221,200` bytes / `0x00406910`, `decoded_size=14,633,113` B / `13.955 MiB`, SHA-256 `d1a22aac2d25851aa84d6227aa7f4080cd57f4d27c5eca78f9a00251267216a2`) adding TX A-MPDU, Short GI, real regulatory country codes, masked WEXT WPA2, and read-only `mtd2ro` non-64K survey;
- **v5.7.0 (`v5.7.0-m3-full-router-repeater-ramboot`, CI run `#45850489679`, `NOT YET VERIFIED` on hardware)** compiled & offline-audited (`32/32` PASS, `7m33s` warm cache, `4,142,576` bytes / `0x003f35f0`, `decoded_size=14,368,249` B / `13.703 MiB` [`2.297 MiB` headroom], SHA-256 `a03fe0204761dbd11b929a3eef78bc4bb80eb3625caec7aac8c7fa12c1fc824a`, `rtl8192cd.ko` `undef=156 missing=0 proc_init=1 giwname=1 giwtxpow=1 wstats=1 nat25=1 bss=694560B`), consolidating a full 4-agent system audit into one complete router + Wi-Fi Repeater + Multi-SSID RAM-boot build:
  - **Full Wi-Fi Repeater & Multi-SSID (`patches/rtl8192cd-4.14-rsd0614.patch`, `packages/rtl8192cd-rsd0614/Makefile`, `harden_source.py`)**: enables `CLIENT_MODE`, `UNIVERSAL_REPEATER` (`wlanX-vxd`), `VXD_DIFF_MAC`, and `MBSSID` (`wlanX-va0`) with distinct per-VIF MACs; supports AP, routed WISP STA, `relayd` L2 pseudo-bridge (`relayd` + `luci-proto-relay`), automatic `RTK_BR_EXT` NAT2.5 bridged STA (`nat25_disable=0` when bridged, `1` when routed), Cross-Band Repeater, Same-Band Universal Repeater (`wlanX` AP + `wlanX-vxd` STA), and Guest Multi-SSID (`wlanX-va0`), plus 8814B/8197G ADDRCAM/StopMBSSID88XX_V2/StopHW88XX/NAPI-close/WEXT scan & stats fixes;
  - **LuCI Wireless Scan, Join & Live Telemetry (`patches/iwinfo-wext-rsd0614.patch`, `build-rsd0614-initramfs.sh`)**: adds `libiwinfo` WEXT compatibility (`radioN -> wlanN` resolution, `rpcd`-safe `.htmode`/`.survey`/`.lookup_phy`, `/proc/<ifname>/sta_info` Associated Stations & `/proc/<ifname>/mib_auth` Encryption parsing, `SIOCGIWNAME` `hwmodelist`/`htmodelist`, `iwinfo` CLI) and fixes upstream LuCI 19.07's `Join Network` `.filter()` truthy-array bug that forced `encryption='sae'` on WPA2 networks while enabling Client mode, BSSID lock, `nat25_disable`, and `auto` channel;
  - **Wired & Memory Hardening**: adds `eth_skb_pad(skb)` in `rtl819x-eth.c` to prevent runt TX OOB DMA on short ARP/TCP ACK frames and trims unused container/core-dump kernel options (`CGROUPS`, `NAMESPACES`, `SWAP`, `AIO`, `COREDUMP`, `FANOTIFY`, `FHANDLE`, `POSIX_MQUEUE`, `SECCOMP`) to reclaim `~265 KiB` of initramfs headroom (`13.703 MiB` vs `13.955 MiB` in `v5.6.5`);
  - **Unchanged safety boundary**: all 6 MTD partitions stay `read-only`, `pcie1` remains disabled, unverified LED GPIOs remain unclaimed, and persistent flash remains **NO-GO**.

## Consolidated bring-up roadmap

1. **M1 (`v5.3.9` -> `v5.4.2` — VERIFIED on physical RSD0614 V1.0)**: Clean `ttyS0` console, read-only `BH25Q64` MTDs, Reset button (`gpio1 4`), `RTL8367S` (`smi_pefgh_24_23`), `RTL8197G` WMAC (`HAL 0x15`), and `PCIe0` `10ec:b814` Link UP.
2. **M2 (`v5.5.1-vg-newdesc-ramboot` — VERIFIED on physical RSD0614 V1.0)**: Full Gigabit wired RAM-boot router (`RTL8367S` `switch0` + `RTL8197FH-VG` 6-dword NIC + LAN `192.168.1.1` ping/SSH + `PCIe0` `10ec:b814` + Reset button).
3. **M3 (`v5.6.4` hardened RAM-boot VERIFIED -> `v5.7.0-m3-full-router-repeater-ramboot` current candidate, `NOT YET VERIFIED` on hardware)**: Complete RAM-boot router with full-MTU Gigabit wired + PPPoE + IPv6 + NAT/`FLOWOFFLOAD` + dual-band Wi-Fi AP (TX A-MPDU + Short GI + real country codes) + full Wi-Fi Repeater (WISP routed STA, `relayd`/`luci-proto-relay` L2 bridge, `RTK_BR_EXT` NAT2.5 bridged STA, Cross-Band & Same-Band Universal Repeater `wlanX-vxd`) + Multi-SSID Guest Wi-Fi (`wlanX-va0`) + LuCI 19.07 Scan/Join/Associated Stations (`libiwinfo` WEXT compat + `iwinfo` CLI). Persistent flash remains **NO-GO** unless an explicit later milestone changes `AGENTS.md`.

## Safety contract

This repository is for **RAM-boot development only** at the current stage.

- Persistent flash remains **NO-GO**.
- Do not add `factory.bin`, `sysupgrade.bin`, `AUTOBURN 1`, `FLW`, erase commands, or automatic router deployment to CI.
- The stock full-flash backup, CFG/calibration data, credentials, HARs, and device-unique material must stay private and must not be committed.
- CI may build and audit artifacts; loading an image into a physical router remains a manual review gate.

## Reproducible inputs

Pinned upstream/donor revisions live in [`SOURCE_LOCK.json`](SOURCE_LOCK.json). The board-specific source is intentionally small and applied on top of the pinned donor/base/driver/feed trees during a build.

## Local Linux / Cloud VM + Windows Docker builds

See [`docs/BUILD_LOCAL.md`](docs/BUILD_LOCAL.md).

On Linux (with persistent `$HOME/.cache/rsd0614-openwrt` seed cache, ~6–10 min warm rebuilds on 2 vCPUs):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 run_tests.py
JOBS=2 bash build-local-linux.sh
```

On Windows PowerShell + Docker Desktop:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Test-RSD0614.ps1
.\Build-RSD0614.ps1 -Jobs 2
```

Review the generated `out/<timestamp>/` evidence before any physical RAM boot.

## GitHub Actions

- **CI / preflight** runs on GitHub-hosted Ubuntu for pushes and pull requests.
- **Full initramfs build** runs only by explicit `workflow_dispatch` or the controlled `.github/build-trigger` path on a GitHub-hosted Ubuntu VM (`JOBS=4`, caching builder image, `dl/`, and toolchain seed via `actions/cache@v4` while compiling `target/linux` and `RSD0614` loader 100% clean every run). It never contacts a router.
- Build outputs and audit evidence are uploaded as workflow artifacts.

This repository is currently public. GitHub explicitly recommends against attaching a self-hosted runner to a public repository. Keep builds on GitHub-hosted runners unless the repository is made private and the runner threat model is reviewed.

## Repository layout

- `RSD0614.dts` — M3 RAM-boot DTS (verified wired Gigabit + Reset button + 40 MHz PCIe0 + `RTL8197G` WMAC + 6 read-only MTDs; `pcie1` disabled).
- `seed-rsd0614-initramfs.config` — initramfs configuration (`kmod-rtl8192cd-rsd0614`, LuCI 19.07 + `uhttpd`, `relayd` + `luci-proto-relay`, `iwinfo`, `wireless-tools`, `ethtool`, `iperf3`, zero-risk kernel diet; `# CONFIG_GDB is not set`).
- `packages/rtl8192cd-rsd0614/Makefile` — out-of-tree pinned Realtek SDK v3.6.0 dual-band Wi-Fi kernel package (AP + STA + Universal Repeater + MBSSID).
- `build-rsd0614-initramfs.sh` — pinned build orchestration inside Linux/Docker with opt-in `CACHE_DIR` toolchain/dl seed support.
- `build-local-linux.sh` — local Linux / Cloud VM cached Docker build wrapper.
- `harden_source.py` — donor-tree isolation, target hardening, M3 wired + dual-band wireless `netifd`/UCI config, and `usr/sbin/rsd0614-survey` staging.
- `deep_audit.py` — binary/DTB/CPIO/SPI-NOR/network/Wi-Fi/LuCI/survey offline audit.
- `test_*.py` — regression suite.
- `patches/` — target-specific kernel, driver, and `libiwinfo` patches (`9996` VG RGMII/PCIe0, `9997` omnibus survey/probe, `9998*` UART, `9999` `BH25Q64`, `rtl8192cd-4.14-rsd0614.patch`, `iwinfo-wext-rsd0614.patch`).
- `docs/` — current audit/build notes.

## License

New project-specific code is covered by [`LICENSE_NEW_CODE.txt`](LICENSE_NEW_CODE.txt). Upstream/donor code is fetched at build time and retains its own licensing.
