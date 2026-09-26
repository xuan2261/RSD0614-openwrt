# CI/CD design

CI is intentionally artifact-only. There is no deployment to the router.

## `preflight.yml`
Runs the Python regression suite on GitHub-hosted Ubuntu for pushes, pull requests, and manual dispatch.

## `build-initramfs.yml`
Manual full build on a GitHub-hosted Ubuntu runner:
1. checks out the repository;
2. builds the pinned Debian Bullseye builder image;
3. runs the regression suite inside the builder;
4. builds OpenWrt in an isolated Docker named volume;
5. runs artifact and deep offline audits;
6. uploads build evidence and the initramfs candidate as an Actions artifact;
7. removes the ephemeral Docker volume.

The workflow grants the `GITHUB_TOKEN` only `contents: read`.
