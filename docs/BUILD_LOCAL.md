# RSD0614 OpenWrt v5.3 — serial diagnostic

This is a diagnostic rebuild of the v5.2.1 pipeline.

Run:

    Set-ExecutionPolicy -Scope Process Bypass
    .\Test-RSD0614.ps1

Require:

    LOCAL_REGRESSION: 89 tests; failures=0; errors=0
    PREFLIGHT EXECUTION PASS

Then:

    .\Build-RSD0614.ps1 -Jobs 2

Do not boot the old v5.2.1 image for this experiment. Use only the new v5.3 output.
Persistent flash remains NO-GO.

## v5.3.1 workspace fix

v5.3 changes the port inputs (notably the DTS), so it MUST NOT reuse the v5.2
source/toolchain workspace. The build's fingerprint guard correctly refuses that reuse.

v5.3.1 uses a new Docker named volume:

    rsd0614-openwrt-v53-work

The old `rsd0614-openwrt-v52-work` volume is intentionally preserved.

Run:

    Set-ExecutionPolicy -Scope Process Bypass
    .\Test-RSD0614.ps1

Then:

    .\Build-RSD0614.ps1 -Jobs 2

Do not delete the old volume and do not use `docker volume prune`.
