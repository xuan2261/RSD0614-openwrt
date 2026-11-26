# RSD0614 OpenWrt v5.5.1 — M2 wired Gigabit (VG 6-dword NIC) + PCIe0 RAM-boot pipeline

This build is intended for controlled **RAM boot** qualification (`v5.5.1-vg-newdesc-ramboot`; router hardware runtime `NOT YET VERIFIED`).

Safety state:
- `spi0` (`sheipa-spi` with bounded polling timeouts + conservative single-lane `BH25Q64` `0x684017` profile, hardware-verified in `v5.4.1`) is enabled strictly for **read-only** MTD inspection across all 6 `read-only` partitions (`CONFIG_MTD_SPLIT_*` disabled);
- hardware-verified wired peripherals are enabled in `RSD0614.dts`: `gpio0`/`gpio1`, Reset button (`&gpio1 4 GPIO_ACTIVE_LOW`), external `RTL8367S` switch (`0x6367`/`0x0020`, `gpio1 24` SCK / `gpio1 23` SDA, `cpu_port=6`, LAN `0..3` VID2 `eth0.2` `192.168.1.1/24`, WAN `4` VID1 `eth0.1` DHCP), `&ethernet` (`RTL8197FH-VG` native 6-dword new-descriptor RX/TX engine `CPUICR1=0x001861d3` + runtime `desc_mode` A/B fallback + post-`TRXRDY` reg re-verification + runout ISR storm guard + RGMII pad preservation `0x579fff7f` + `PITCR CF_FIX_IPG=1` + `P0GMIICR RX_delay=7` + `hwnat=0` + `fabric_gw_rearm=0`), and hardware-verified `&pcie0` (`40 MHz` XTAL + VG MDIO `0x08=0x3101` for `10ec:b814` `RTL8814BR`);
- passive `/proc/rsd0614_hw_survey` (`0444`, `.write = NULL`), opt-in manual `/proc/rsd0614_probe` (`0600`), and sanitized `/usr/sbin/rsd0614-survey` remain built in without auto-execution at boot and without reading or printing secret `cfg`/`cpe`/`cfm` partition payloads;
- `pcie1` (unverified, shares IRQ 6) and on-SoC 2.4 GHz `wmac` (`RTL8197G` `HAL 0x15`, awaiting M3 SDK v3.6.0 dual-band Wi-Fi) remain disabled in `RSD0614.dts` with WMAC IRQ `BIT(29)` masked;
- enabled startup services do not call `mount_root`;
- `realtek,rtl8197f-uart` dispatches register layout and LCR/divisor quirks at runtime by SoC ID (`RTL8197FH-VG` `0x81970001` `vg-std` hardware-verified in `v5.3.9`..`v5.5.0`);
- persistent flash remains **NO-GO**.

## Local Linux / Cloud VM build (recommended fast path)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 run_tests.py
JOBS=2 bash build-local-linux.sh
```

- `build-local-linux.sh` uses a fresh ephemeral Docker named volume per build (`rsd0614-openwrt-v551-work-<run_id>`, removed on exit) while persisting the pinned Debian Bullseye builder image (`builder/builder.tar.zst`), upstream tarballs (`cache/dl/`), and host/toolchain seed (`cache/seed/toolchain-<tc_key>.tar.zst`) under `${RSD0614_CACHE_ROOT:-$HOME/.cache/rsd0614-openwrt}`.
- Target packages, Linux `4.14.187`, `RSD0614.dts`, CPIO rootfs, and the `BOARD="RSD0614"` LZMA loader are **never** cached and always compile fresh (~13 minutes warm on 2 vCPUs; ~5–6 minutes warm on 4-vCPU GitHub Actions).

## Local Windows PowerShell preflight & build

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Test-RSD0614.ps1
.\Build-RSD0614.ps1 -Jobs 2
```

Require preflight:

```text
LOCAL_REGRESSION: 129 tests; failures=0; errors=0
PREFLIGHT EXECUTION PASS
```

v5.5.1 PowerShell builds use the dedicated Docker volume:

```text
rsd0614-openwrt-v551-work
```

Older `v5.2` through `v5.5.0` work volumes are intentionally preserved. Do not delete them and do not run `docker volume prune`.

A successful compile is not boot proof. Review `BUILD_RESULT.txt`, `BINARY_AUDIT.json`, provenance, the candidate SHA-256 and UART/runtime evidence before changing any hardware gate.
