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
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) is hardware-verified on physical RSD0614 V1.0** (`soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0`, `BOOTSTRAP=0x41258ee0` 40 MHz XTAL / 1000 MHz CPU / 64 MiB DDR2-533, `BH25Q64` `0x684017`, clean `ttyS0` 16550A TX/RX console, interactive BusyBox `ash` shell, `/proc/interrupts` `irq17=102, ERR=0`);
- the **v5.4.1 (`v5.4.1-omnibus-readonly-survey`) candidate** consolidates read-only `spi0` / `BH25Q64` (`0x684017`) MTD inspection (`mtd0..mtd5` `read-only;`), passive `/proc/rsd0614_hw_survey` (`0444`), opt-in post-survey one-shot `/proc/rsd0614_probe` (`0600`: `smi`, `wmac`, `pcie0`), and sanitized on-demand `/usr/sbin/rsd0614-survey` into **one RAM-boot qualification image** (`NOT YET VERIFIED` on hardware), while **PCIe0/1, WMAC, and Ethernet remain disabled at boot** and persistent flash remains **NO-GO**.

## Consolidated 3-step bring-up roadmap

1. **M1 (`v5.4.1-omnibus-readonly-survey` — current candidate, hardware runtime `NOT YET VERIFIED`)**: Accelerate CI/local OpenWrt builds via `dl/` + host/toolchain `.tar.zst` seed caching (`# CONFIG_GDB is not set`, CI `JOBS=4`, `build-local-linux.sh`), and gather all remaining board evidence (SPI NOR headers, `SYSC`/`BOOTSTRAP`/`BOND_OPTION`/`PINMUX`/`GPIO`/`SWCORE` registers, button GPIO deltas, pinmux-guarded `RTL8367` SMI ID/extif/pbmp, re-gated 2.4 GHz WMAC cut/HAL ID, and `LTSSM==0x11`-guarded 40 MHz PCIe0 `10ec:b814` ID) in **one single TFTP RAM-boot session**.
2. **M2 (Functional RAM-boot router — `NOT YET VERIFIED`, gated on M1 UART evidence)**: Enable `&ethernet` (`rtl819x-eth` + verified `RTL8367RB` switch/VLANs), verified `gpio-keys`/`gpio-leds`, `&pcie0` 40 MHz bus enumeration, and 2.4 GHz `rtl8192cd` WMAC AP fed by runtime read-only `/dev/mtd1ro` calibration in RAM.
3. **M3 (`RTL8814BR` `10ec:b814` 5 GHz WLAN driver — future milestone)**: Integrate an `RTL8814B` (`10ec:b814`) driver/HAL (neither pinned `ggbruno/openwrt` `rtw88` nor `ADCDS` `rtl8192cd` v3.4.11e contains a driver for `10ec:b814`). Persistent flash remains **NO-GO** unless an explicit later milestone changes `AGENTS.md`.

## Safety contract

This repository is for **RAM-boot development only** at the current stage.

- Persistent flash remains **NO-GO**.
- Do not add `factory.bin`, `sysupgrade.bin`, `AUTOBURN 1`, `FLW`, erase commands, or automatic router deployment to CI.
- The stock full-flash backup, CFG/calibration data, credentials, HARs, and device-unique material must stay private and must not be committed.
- CI may build and audit artifacts; loading an image into a physical router remains a manual review gate.

## Reproducible inputs

Pinned upstream/donor revisions live in [`SOURCE_LOCK.json`](SOURCE_LOCK.json). The board-specific source is intentionally small and applied on top of the pinned donor/base trees during a build.

## Local Linux / Cloud VM + Windows Docker builds

See [`docs/BUILD_LOCAL.md`](docs/BUILD_LOCAL.md).

On Linux (with persistent `$HOME/.cache/rsd0614-openwrt` seed cache, ~5–6 min warm rebuilds on 2 vCPUs):

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

- `RSD0614.dts` — fail-closed diagnostic DTS.
- `seed-rsd0614-initramfs.config` — minimal initramfs configuration (`# CONFIG_GDB is not set`).
- `build-rsd0614-initramfs.sh` — pinned build orchestration inside Linux/Docker with opt-in `CACHE_DIR` toolchain/dl seed support.
- `build-local-linux.sh` — local Linux / Cloud VM cached Docker build wrapper.
- `harden_source.py` — donor-tree isolation, target hardening, and `usr/sbin/rsd0614-survey` staging.
- `deep_audit.py` — binary/DTB/CPIO/SPI-NOR/survey offline audit.
- `test_*.py` — regression suite.
- `patches/` — target-specific kernel patches (`9997` omnibus survey/probe, `9998*` UART, `9999` `BH25Q64`).
- `docs/` — current audit/build notes.

## License

New project-specific code is covered by [`LICENSE_NEW_CODE.txt`](LICENSE_NEW_CODE.txt). Upstream/donor code is fetched at build time and retains its own licensing.
