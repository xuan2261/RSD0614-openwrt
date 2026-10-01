# Current bring-up status

## Execution-passed evidence

- UART and RealTek bootloader command mode on the physical RSD0614.
- 64 MiB RAM and 8 MiB BH25Q64 NOR identity.
- TFTP RAM boot with `AUTOBURN 0`.
- Linux 4.14.187 boots through kernel init and OpenWrt `procd` userspace.
- v5.3.7 bounded instrumentation identified the persistent UART interrupt as overwhelmingly RX timeout.

## Root-cause evidence

v5.3.7 hardware snapshot:

```text
n=512 msi=0 thri=52 rdi=0 rlsi=0 busy=0 timeout=441 other=19
iir=cc->lsr:cc->msr:cc->usr:cc->rx:cc
lsr=61 msr=10 usr=00 rbr=00 ier=05 lcr=13 stsr=000000b0 last_lcr=13
```

This proves:
- the dominant source is RX timeout (`IIR ID 0x0c`);
- BUSY is not the active source;
- LSR still reports data-ready;
- reading LSR/MSR/USR/RX does not clear the interrupt;
- hardware and saved LCR are both `0x13`.

OpenWrt base patch `0004-rtl8197f-dw-uart.patch` has two structural defects relevant to this state:

1. Its RTL8197F LCR adjustment compares the entire LCR value to `UART_LCR_WLEN7/8`. Composite values such as observed `0x13` bypass the translation entirely. RTL8197F requires WLEN translation on bits [1:0] while preserving parity/stop/DLAB bits.

2. It remaps logical register 0 to RTL8197F RX/TX index 9 without DLAB awareness. Generic 8250 also uses logical register 0 for DLL while DLAB=1, so divisor-latch accesses can be redirected to RBR/THR. Vendor RTL8197F keeps DLL/DLM at raw indices 0/1 while RX/TX use index 9.

## v5.3.8 fix scope

- Preserve base RX/TX index 9 mapping for normal DLAB=0 data access.
- Translate only LCR WLEN[1:0]: standard 7/8-bit encodings 2/3 become RTL8197F 0/1 while all other LCR bits are preserved.
- Install RTL8197F-specific `dl_read/dl_write` callbacks that access raw DLL/DLM offsets 0/1 under DLAB.
- Retain v5.3.6 BUSY recovery.
- Retain v5.3.7 bounded IRQ diagnostic during hardware validation.
- Keep SPI, Ethernet, PCIe0/1 and WMAC disabled.
- Keep persistent-root automatic paths suppressed.

Expected hardware validation:
- final LCR should reflect corrected composite encoding (observed `0x13` class becomes `0x11`);
- Enter must not produce a persistent `serial8250: too much work for irq17` storm;
- askconsole should receive UART input.

## Verification boundary

- v5.3.7 compile/offline audit: PASS.
- v5.3.7 hardware diagnosis: PASS; root cause narrowed to broken RTL8197F register/LCR semantics.
- v5.3.8 preflight/build/runtime: NOT YET VERIFIED.
- Persistent flash: NO-GO.
