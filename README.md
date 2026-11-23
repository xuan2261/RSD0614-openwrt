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
- **v5.3.9 (`v5.3.9-uart-soc-id-dispatch`) & v5.4.1 (`v5.4.1-omnibus-readonly-survey`) hardware-verified on physical RSD0614 V1.0**:
  - Clean `ttyS0` 16550A TX/RX console without `keep_bootcon` (`soc_id=0x81970001 mode=vg-std`, `BOOTSTRAP=0x41258ee0` 40 MHz XTAL / 1000 MHz CPU / 64 MiB DDR2-533, `BOND_OPTION=0x4` `97FN`, `irq17=105, ERR=0`);
  - Read-only `spi0` / `BH25Q64` (`0x684017`, `div 28`, 8 MiB) across all 6 `read-only` MTD partitions (`mtd0..mtd5`, `flags=0x800`), stock `mtd2ro` `cr6c` header (`start=0x80a00000`, `burn=0x30000`, `len=0x256c02`);
  - Physical button verified on **`GPIO_PEFGH` bit 4 (`&gpio1 4 GPIO_ACTIVE_LOW`, `BSP_GPIO_PIN_E4`, `xor=0x10`)**;
  - Live RGMII trunk on `SWCORE` Port 0 verified (`PITCR=0x1`, `P0GMIICR=0x00037d57` RX delay `7`, `PCRP0=0x16972039`, `EXTPCR0=0x000c0000`, `RGMII_PAD_CTRL=0x579fff7f`, `PINMUX_SEL2=0x0`);
- the **v5.4.2 (`v5.4.2-omnibus-readonly-survey`) candidate** fixes `/proc/rsd0614_probe` split-newline write handling, speeds up `mtd2ro` rootfs offset detection to `<0.05s`, and upgrades `smi` to safe 3-way `RTL8367` bus auto-discovery (`SWCORE` Clause-22 MDIO + mux-restored `C2/C3` SMI + `G7/H0` SMI) alongside `wmac` and `pcie0` (`NOT YET VERIFIED` on hardware), while **PCIe0/1, WMAC, and Ethernet remain disabled at boot** and persistent flash remains **NO-GO**.

## Consolidated 3-step bring-up roadmap

1. **M1b (`v5.4.2-omnibus-readonly-survey` — current candidate, hardware runtime `NOT YET VERIFIED`)**: Run `rsd0614-survey probe-all` in one shot to complete `RTL8367` MDIO/SMI switch ID + 2.4 GHz `WMAC` cut/HAL ID + 40 MHz `PCIe0` `10ec:b814` link-up verification.
2. **M2 (Functional RAM-boot router — `NOT YET VERIFIED`, gated on M1b UART evidence)**: Enable `&ethernet` (preserving RSD0614's verified `P0GMIICR=0x00037d57` RX delay `7` / `RGMII_PAD_CTRL=0x579fff7f` + `RTL8367RB` LAN `0..3` / WAN `4` VLANs), verified `&gpio1 4` button, `&pcie0` 40 MHz bus enumeration, and 2.4 GHz `rtl8192cd` WMAC AP (`0x81970001` VG ID + `97FN` bond `0x4` + runtime read-only `/dev/mtd1ro` calibration in RAM).
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
