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
- **v5.6.1 (`v5.6.1-m3-wifi-pcie-hardened-ramboot`, CI run `#45434537894`) physical RAM-boot verified `PCIe0` first-attempt link-up (`LTSSM=0x039b4f11`, `link_up=1`) and `rtl8192cd.ko` dual-radio attach (`wlan0` `RTL8814BR` 5 GHz + `wlan1` `RTL8197G` 2.4 GHz, read-only `/dev/mtd1` `65536B` Tenda KV factory calibration loaded, DHCP `192.168.1.106` & `ping` live)** while isolating the three runtime blockers fixed in **v5.6.2 (`v5.6.2-m3-wifi-mtu-hardened-ramboot`, `NOT YET VERIFIED` on hardware)**:
  - **Full-MTU (`1500B` IP / `1526B` RGMII trunk) wired Gigabit fix**: programs `RTL8367S` (`0x6367`) `CFG0`/`CFG1` (`0x088c`/`0x088d`) = `0x0610` (`1552B`, replacing the `1522B` default that truncated `1526B` CPU-tag + `802.1Q` LuCI JS / SSH `KEXINIT` frames) and selects `CFG0` in both `rtl8367s_cpu_tag_enable()` and `rtl8367b_setup()` (preserving `1552B` across `swconfig` apply), preserves `CPUICR` bit 29 (`BUSBURST_128WORDS`) in `_New_swNic_send`, linearizes nonlinear TX SKBs, sets `MACCR` `CF_FCDSC=0x48`, and raises `USEDDSC` pressure/stall threshold from `256` to `400` (eliminating false `PRESSURE` spam & false 5s `RX-STALL WEDGE` resets at normal `USEDDSC=345`);
  - **Dual-band Wi-Fi AP bring-up & WEXT/LuCI hardening**: enables `_INCLUDE_PROC_FS_` on Linux 4.14 (`/proc/wlan0`, `/proc/wlan1`), switches `/lib/netifd/wireless/rtl8192cd.sh` device checks from `/proc/.../mib_all` to `/sys/class/net/...` (fixing `NO_DEVICE` abort before `ifconfig wlan0/wlan1 up`), adds `SET_NETDEV_DEV`, extends `8814B` TX reclaim kicks, wires AP-safe `rtl_giwname` (`SIOCGIWNAME` for `iwconfig`), populates LuCI `wireless.js` `rtl8192cd` modes/widths/channels + empty-save guard, sets `vm.min_free_kbytes=2048`, and adds `rsd0614-survey net|diag`;
  - **Unchanged safety boundary**: all 6 MTD partitions stay `read-only`, `pcie1` remains disabled, unverified LED GPIOs remain unclaimed, and persistent flash remains **NO-GO**.

## Consolidated bring-up roadmap

1. **M1 (`v5.3.9` -> `v5.4.2` — VERIFIED on physical RSD0614 V1.0)**: Clean `ttyS0` console, read-only `BH25Q64` MTDs, Reset button (`gpio1 4`), `RTL8367S` (`smi_pefgh_24_23`), `RTL8197G` WMAC (`HAL 0x15`), and `PCIe0` `10ec:b814` Link UP.
2. **M2 (`v5.5.1-vg-newdesc-ramboot` — VERIFIED on physical RSD0614 V1.0)**: Full Gigabit wired RAM-boot router (`RTL8367S` `switch0` + `RTL8197FH-VG` 6-dword NIC + LAN `192.168.1.1` ping/SSH + `PCIe0` `10ec:b814` + Reset button).
3. **M3 (`v5.6.2-m3-wifi-mtu-hardened-ramboot` — current candidate, `NOT YET VERIFIED` on hardware)**: Full-MTU (`1552B` trunk) Gigabit wired + dual-band Wi-Fi AP (`RSD0614-OpenWrt-5G` + `RSD0614-OpenWrt-2G`, 64 MiB RAM-safe rings, coherent DMA, read-only runtime `"cfg"` calibration, `/proc/wlan*` + `iwconfig`) + LuCI 19.07 web UI + diagnostic/benchmark tools in RAM. Persistent flash remains **NO-GO** unless an explicit later milestone changes `AGENTS.md`.

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
- `seed-rsd0614-initramfs.config` — initramfs configuration (`kmod-rtl8192cd-rsd0614`, LuCI 19.07 + `uhttpd`, `wireless-tools`, `ethtool`, `iperf3`; `# CONFIG_GDB is not set`).
- `packages/rtl8192cd-rsd0614/Makefile` — out-of-tree pinned Realtek SDK v3.6.0 dual-band Wi-Fi kernel package.
- `build-rsd0614-initramfs.sh` — pinned build orchestration inside Linux/Docker with opt-in `CACHE_DIR` toolchain/dl seed support.
- `build-local-linux.sh` — local Linux / Cloud VM cached Docker build wrapper.
- `harden_source.py` — donor-tree isolation, target hardening, M3 wired + dual-band wireless `netifd`/UCI config, and `usr/sbin/rsd0614-survey` staging.
- `deep_audit.py` — binary/DTB/CPIO/SPI-NOR/network/Wi-Fi/LuCI/survey offline audit.
- `test_*.py` — regression suite.
- `patches/` — target-specific kernel and driver patches (`9996` VG RGMII/PCIe0, `9997` omnibus survey/probe, `9998*` UART, `9999` `BH25Q64`, `rtl8192cd-4.14-rsd0614.patch`).
- `docs/` — current audit/build notes.

## License

New project-specific code is covered by [`LICENSE_NEW_CODE.txt`](LICENSE_NEW_CODE.txt). Upstream/donor code is fetched at build time and retains its own licensing.
