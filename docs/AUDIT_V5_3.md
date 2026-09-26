# RSD0614 v5.3 serial diagnostic

The v5.2.1 RAM boot reaches Linux and stops immediately after the 8250 console handoff.
No userspace shell has started at that point, so lack of keyboard response is expected.

The next high-value suspect is the RTL8197F Sheipa SPI/NOR probe. The pinned driver contains
unbounded polling loops during flash/controller initialization. v5.3 isolates this by keeping
`spi0` disabled and adds `initcall_debug ignore_loglevel`.

Interpretation:
- boot progresses: SPI probe is confirmed as the blocker;
- boot still stops: initcall tracing should identify the last executed initcall.

Persistent flash remains NO-GO.
