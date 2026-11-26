# CI/CD design

CI is intentionally artifact-only. There is no deployment to the router.

## `preflight.yml`
Runs the Python regression suite on GitHub-hosted Ubuntu for pushes, pull requests, and manual dispatch.

## `build-initramfs.yml`
Manual full build on a GitHub-hosted Ubuntu runner (`JOBS=4` default, per-ref concurrency canceling superseded branch runs while never canceling `main`):
1. checks out the repository;
2. restores/saves the pinned Debian Bullseye builder image (`~/.cache/rsd0614-builder`), upstream OpenWrt tarballs (`~/.cache/rsd0614-openwrt-cache/dl`), and host/toolchain `.tar.zst` seed (`~/.cache/rsd0614-openwrt-cache/seed`) via `actions/cache@v4`;
3. runs the regression suite inside the builder (`--network=none`);
4. builds OpenWrt in an isolated ephemeral Docker named volume (hydrating `dl/` and `staging_dir/{host,hostpkg,toolchain-*}` while always compiling `target/linux`, DTB, CPIO, and `RSD0614` loader clean from scratch);
5. runs artifact and deep offline audits;
6. uploads build evidence and the initramfs candidate as an Actions artifact;
7. removes the ephemeral Docker volume.

The workflow grants the `GITHUB_TOKEN` only `contents: read`.
