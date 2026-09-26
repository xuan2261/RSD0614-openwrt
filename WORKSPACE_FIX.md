# RSD0614 v5.3.1 workspace fix

## Root cause

The v5.3 build changed port inputs but `Build-RSD0614.ps1` still mounted
`rsd0614-openwrt-v52-work`. `build-rsd0614-initramfs.sh` stores a port-input
fingerprint in that persistent volume and intentionally refuses to continue
when the new inputs differ.

This is an expected fail-closed guard, not an OpenWrt compile failure.

## Fix

Use a new named volume for v5.3:

- volume: `rsd0614-openwrt-v53-work`
- ownership label: `rsd0614.work=v5.3`

The v5.2 volume is preserved unchanged.

## Verification boundary

Local regression and static wrapper checks can be run here.
Actual Docker/OpenWrt compilation remains NOT YET VERIFIED until run on the
user's Docker engine.
