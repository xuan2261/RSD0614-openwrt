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

Hardware variant correlation:
- Rock Space RSD0614 V1.0 (hardware sibling of Tenda AC19/AC21/AC23: `RTL8197FH-VG` + `RTL8367RB` + `RTL8814BR` `10ec:b814` + `BH25Q64` 8 MiB) runs **RTL8197FH-VG** (`(REG32(0xB8000000) & 0xFFFFF000) == 0x81970000`), where UART0 uses standard 16550/DW-APB semantics (**RBR/THR at `+0x00`**, **`WLEN8 = 0x03`**).
- `early0` (`prom.c`) dynamically checks `0xB8000000` and therefore outputs normally, whereas OpenWrt base patch `0004-rtl8197f-dw-uart.patch` unconditionally hardcoded `tx_reg = rx_reg = 9 (+0x24)` and `adjlcr = true` (which apply only to non-VG `RTL8197F` `0x8197F000`). That explains silent `ttyS0` TX and why reading RX at `+0x24` left `+0x00` unread (`lsr=61`, `rbr=00`, `iir=cc->rx:cc`, `timeout=441`).
- v5.3.8 still retained `+0x24`, translated `LCR 0x13 -> 0x11` (turning 8N1 into 6N1 on VG), wrote untranslated `LCR` before `dw8250_check_lcr()` (causing `dw8250_force_idle()` FIFO resets on every LCR write), and kept `p->flags = UPF_SKIP_TEST| UPF_FIXED_TYPE` clobbering `UPF_SHARE_IRQ | UPF_FIXED_PORT`.

## v5.3.9 fix scope

- Read SoC ID at runtime from `realtek,rtl819x-sysc` (`0x00`) and classify `is_non_vg = ((soc_id & 0xFFFFF000U) == 0x8197F000U)`.
- On **RTL8197FH-VG** (`mode=vg-std`): use `tx_reg = UART_TX (0)`, `rx_reg = UART_RX (0)`, `adjlcr = false`, and standard `dl_read`/`dl_write`.
- On **non-VG RTL8197F** (`mode=non-vg`): retain `tx_reg = 9`, `rx_reg = 9`, `adjlcr = true`, and raw `rtl8197f_dl_read`/`rtl8197f_dl_write`.
- Translate LCR via `rtl8197f_translate_lcr()` **before** `writeb`/`writel`/`iowrite32be` in `dw8250_serial_out`, `dw8250_serial_out32`, and `dw8250_serial_out32be`, removing late translation in `dw8250_check_lcr()` so `dw8250_force_idle()` is not triggered spuriously.
- Preserve `UPF_SHARE_IRQ | UPF_FIXED_PORT` via `p->flags |= UPF_SKIP_TEST | UPF_FIXED_TYPE;` without assigning `p->fifosize` in probe.
- Guard both v5.3.6 BUSY LCR replay and v5.3.7 bounded 512-pass IRQ diagnostics with `is_rtl8197f` so both variants retain full observability and recovery.
- Keep SPI, Ethernet, PCIe0/1 and WMAC disabled, and keep persistent-root automatic paths suppressed.

Expected hardware validation on RSD0614 (`RTL8197FH-VG`):
- kernel log prints `rtl8197f-uart: soc_id=0x81970001 mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0` (exact stepping nibble from hardware);
- `ttyS0` transmits normally after bootconsole handoff and drains RX at `+0x00` without an IRQ17 RX-timeout storm;
- interactive `askconsole` shell responds over UART.

## Verification boundary

- v5.3.7 compile/offline audit & hardware diagnosis: PASS.
- v5.3.8 compile/offline audit: PASS (superseded before hardware run due to VG/non-VG SoC-ID split).
- v5.3.9 preflight (`45026364712`) & full compile/offline structural audit (`45026415476` at commit `221aae1`): PASS (`openwrt-realtek-rtl8197f-RSD0614-initramfs-kernel.bin`, `2,928,560` bytes, SHA-256 `e8199f3abde18b91c460df6eef265218226e33fb6bbad2a3fb09b1219ad65768`, ELF `_end = 0x809e31d0`, port input fingerprint `2d26aaa7acf7e2e185ebb8d85fc67d0ce81ad7a29efd3722f48f386e8bd620f0`).
- v5.3.9 hardware runtime: NOT YET VERIFIED (`RAM_BOOT_AUTHORIZED=NO`).
- Persistent flash: NO-GO.
