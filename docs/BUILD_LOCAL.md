# RSD0614 OpenWrt v5.4.1 — omnibus read-only hardware qualification & cached build pipeline

This build is intended for controlled **RAM boot** qualification (`v5.4.1-omnibus-readonly-survey`; router hardware runtime `NOT YET VERIFIED`).

Safety state:
- `spi0` (`sheipa-spi` with bounded polling timeouts + conservative single-lane `BH25Q64` `0x684017` profile) is enabled strictly for **read-only** MTD inspection across all 6 `read-only` partitions (`CONFIG_MTD_SPLIT_*` disabled);
- passive `/proc/rsd0614_hw_survey` (`0444`, `.write = NULL`), opt-in manual `/proc/rsd0614_probe` (`0600`: `smi`, `wmac`, `pcie0`), and sanitized `/usr/sbin/rsd0614-survey` are built in without auto-execution at boot and without reading or printing secret `cfg`/`cpe`/`cfm` partition payloads;
- Ethernet, PCIe0/1 and WMAC remain disabled in the RSD0614 DTB;
- direct NET/PCIe/WiFi IRQ sources are cleared and masked;
- enabled startup services do not call `mount_root`;
- generic board detection does not synthesize `eth0` / `eth1`;
- `realtek,rtl8197f-uart` dispatches register layout and LCR/divisor quirks at runtime by SoC ID (`RTL8197FH-VG` `0x81970001` `vg-std` hardware-verified in `v5.3.9`);
- persistent flash remains **NO-GO**.

## Local Linux / Cloud VM build (recommended fast path)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 run_tests.py
JOBS=2 bash build-local-linux.sh
```

- `build-local-linux.sh` uses a fresh ephemeral Docker named volume per build (`rsd0614-openwrt-v541-work-<run_id>`, removed on exit) while persisting the pinned Debian Bullseye builder image (`builder/builder.tar.zst`), upstream tarballs (`cache/dl/`), and host/toolchain seed (`cache/seed/toolchain-<tc_key>.tar.zst`) under `${RSD0614_CACHE_ROOT:-$HOME/.cache/rsd0614-openwrt}`.
- Target packages, Linux `4.14.187`, `RSD0614.dts`, CPIO rootfs, and the `BOARD="RSD0614"` LZMA loader are **never** cached and always compile fresh (~5–6 minutes warm on 2 vCPUs; ~3–4 minutes warm on 4-vCPU GitHub Actions).

## Local Windows PowerShell preflight & build

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Test-RSD0614.ps1
.\Build-RSD0614.ps1 -Jobs 2
```

Require preflight:

```text
LOCAL_REGRESSION: 127 tests; failures=0; errors=0
PREFLIGHT EXECUTION PASS
```

v5.4.1 PowerShell builds use the dedicated Docker volume:

```text
rsd0614-openwrt-v541-work
```

Older `v5.2` through `v5.4.0` work volumes are intentionally preserved. Do not delete them and do not run `docker volume prune`.

A successful compile is not boot proof. Review `BUILD_RESULT.txt`, `BINARY_AUDIT.json`, provenance, the candidate SHA-256 and UART/runtime evidence before changing any hardware gate.
