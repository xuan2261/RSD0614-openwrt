# Repository instructions

## Mission
Maintain a fail-closed, evidence-driven RAM-boot port for Rock Space RSD0614 V1.0.

## Hard safety invariants
- Persistent flash is NO-GO until an explicit later milestone changes this contract.
- Never commit device-unique full-flash dumps, CFG/calibration contents, credentials, HARs, or stock configuration backups.
- Do not introduce `factory.bin`, `sysupgrade.bin`, `AUTOBURN 1`, RealTek `FLW`, erase commands, or automated router deployment.
- CI/build jobs must never contact the physical router.
- Preserve exact pinned donor/base commits in `SOURCE_LOCK.json` unless a deliberate migration is reviewed.

## Verification
- Run `python3 run_tests.py` after source/test changes.
- A successful build is not boot proof. Preserve `NOT YET VERIFIED` until actual UART/runtime evidence exists.
- Keep board peripherals disabled until target-specific evidence supports enabling them.
