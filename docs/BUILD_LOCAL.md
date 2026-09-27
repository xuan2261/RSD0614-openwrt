# RSD0614 OpenWrt v5.3.3 — pre-RAM fail-closed diagnostic

This build is serial-only and intended for controlled **RAM boot** qualification.

Safety state:
- SPI, Ethernet, PCIe and WMAC remain disabled in the RSD0614 DTB.
- direct NET/PCIe/WiFi IRQ sources are cleared and masked;
- enabled startup services do not call `mount_root`;
- generic board detection does not synthesize `eth0` / `eth1`;
- persistent flash remains **NO-GO**.

## Local preflight

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Test-RSD0614.ps1
```

Require:

```text
LOCAL_REGRESSION: 101 tests; failures=0; errors=0
PREFLIGHT EXECUTION PASS
```

## Local build

```powershell
.\Build-RSD0614.ps1 -Jobs 2
```

v5.3.3 uses the dedicated Docker volume:

```text
rsd0614-openwrt-v533-work
```

Older v5.2/v5.3/v5.3.2 work volumes are intentionally preserved. Do not delete them and do not run `docker volume prune`.

A successful compile is not boot proof. Review `BUILD_RESULT.txt`, `BINARY_AUDIT.json`, provenance, the candidate SHA-256 and UART/runtime evidence before changing any hardware gate.
