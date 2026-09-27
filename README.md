# Rock Space RSD0614 OpenWrt bring-up

Experimental, evidence-driven OpenWrt/Linux bring-up for **Rock Space RSD0614 V1.0** on the Realtek RTL8197F family.

## Current milestone

The project has already verified on a physical RSD0614 unit:

- 64 MiB DDR2 RAM;
- BH25Q64 8 MiB SPI NOR;
- UART `115200 8N1` and RealTek bootloader command mode;
- TFTP RAM load at `0x81000000` with `AUTOBURN 0`;
- a first OpenWrt 4.14.187 RAM-boot reached Linux and selected the RSD0614 DTB;
- the first candidate stopped shortly after the serial-console handoff, before userspace;
- the current **v5.3.3 pre-RAM diagnostic candidate disables SPI, PCIe, WMAC and Ethernet**, adds `initcall_debug ignore_loglevel`, clears/masks unused direct NET/PCIe/WiFi IRQ sources, removes enabled automatic `mount_root` paths, and suppresses generic `eth0`/`eth1` synthesis.

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
