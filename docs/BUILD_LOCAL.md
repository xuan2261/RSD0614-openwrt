# RSD0614 OpenWrt v5.4.0 — read-only SPI NOR (`BH25Q64`) RAM-boot qualification

This build is intended for controlled **RAM boot** qualification (`v5.4.0-spi-nor-readonly`).

Safety state:
- `spi0` (`sheipa-spi` with bounded polling timeouts + conservative single-lane `BH25Q64` `0x684017` profile) is enabled strictly for **read-only** MTD inspection across all 6 `read-only` partitions (`CONFIG_MTD_SPLIT_*` disabled);
- Ethernet, PCIe0/1 and WMAC remain disabled in the RSD0614 DTB;
- direct NET/PCIe/WiFi IRQ sources are cleared and masked;
- enabled startup services do not call `mount_root`;
- generic board detection does not synthesize `eth0` / `eth1`;
- `realtek,rtl8197f-uart` dispatches register layout and LCR/divisor quirks at runtime by SoC ID (`RTL8197FH-VG` `0x81970001` `vg-std` hardware-verified);
- persistent flash remains **NO-GO**.

## Local preflight

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Test-RSD0614.ps1
```

Require:

```text
LOCAL_REGRESSION: 121 tests; failures=0; errors=0
PREFLIGHT EXECUTION PASS
```

## Local build

```powershell
.\Build-RSD0614.ps1 -Jobs 2
```

v5.4.0 uses the dedicated Docker volume:

```text
rsd0614-openwrt-v540-work
```

Older `v5.2` through `v5.3.9` work volumes are intentionally preserved. Do not delete them and do not run `docker volume prune`.

A successful compile is not boot proof. Review `BUILD_RESULT.txt`, `BINARY_AUDIT.json`, provenance, the candidate SHA-256 and UART/runtime evidence before changing any hardware gate.
