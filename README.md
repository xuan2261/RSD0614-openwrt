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
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) is hardware-verified on physical RSD0614 V1.0** (`soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0`, clean `ttyS0` 16550A TX/RX console, interactive BusyBox `ash` shell, `/proc/interrupts` `irq17=102, ERR=0`);
- the current **v5.4.0 (`v5.4.0-spi-nor-readonly`) candidate** retires `keep_bootcon` and enables conservative read-only `spi0` / `BH25Q64` (`0x684017`) MTD probing across all 6 `read-only` partitions (`NOT YET VERIFIED` on hardware), while **PCIe0/1, WMAC and Ethernet remain disabled** and persistent flash remains **NO-GO**.

## Safety contract

This repository is for **RAM-boot development only** at the current stage.

- Persistent flash remains **NO-GO**.
- Do not add `factory.bin`, `sysupgrade.bin`, `AUTOBURN 1`, `FLW`, erase commands, or automatic router deployment to CI.
- The stock full-flash backup, CFG/calibration data, credentials, HARs, and device-unique material must stay private and must not be committed.
- CI may build and audit artifacts; loading an image into a physical router remains a manual review gate.

## Reproducible inputs

Pinned upstream/donor revisions live in [`SOURCE_LOCK.json`](SOURCE_LOCK.json). The board-specific source is intentionally small and applied on top of the pinned donor/base trees during a build.

## Local Windows + Docker build

See [`docs/BUILD_LOCAL.md`](docs/BUILD_LOCAL.md). The quick path is:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Test-RSD0614.ps1
.\Build-RSD0614.ps1 -Jobs 2
```

Review the generated `out/<timestamp>/` evidence before any physical RAM boot.

## GitHub Actions

- **CI / preflight** runs on GitHub-hosted Ubuntu for pushes and pull requests.
- **Full initramfs build** runs only by explicit `workflow_dispatch` or the controlled `.github/build-trigger` path on a GitHub-hosted Ubuntu VM. It never contacts a router.
- Build outputs and audit evidence are uploaded as workflow artifacts.

This repository is currently public. GitHub explicitly recommends against attaching a self-hosted runner to a public repository. Keep builds on GitHub-hosted runners unless the repository is made private and the runner threat model is reviewed.

## Repository layout

- `RSD0614.dts` — fail-closed diagnostic DTS.
- `seed-rsd0614-initramfs.config` — minimal initramfs configuration.
- `build-rsd0614-initramfs.sh` — pinned build orchestration inside Linux/Docker.
- `harden_source.py` — donor-tree isolation and target hardening.
- `deep_audit.py` — binary/DTB/CPIO/SPI-NOR offline audit.
- `test_*.py` — regression suite.
- `patches/` — target-specific kernel patches.
- `docs/` — current audit/build notes.

## License

New project-specific code is covered by [`LICENSE_NEW_CODE.txt`](LICENSE_NEW_CODE.txt). Upstream/donor code is fetched at build time and retains its own licensing.
