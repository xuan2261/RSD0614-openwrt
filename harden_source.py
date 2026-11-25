#!/usr/bin/env python3
"""Isolate the dedicated RSD0614 source tree. Does not contact a router."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
BASE='8a0ccb93f3431bcf8f5c5d03d4acc2c8e442de67'; VG_RGMII_PCIE_PATCH_NAME='9996-rsd0614-vg-rgmii-and-pcie.patch'; SURVEY_PATCH_NAME='9997-rsd0614-hw-survey-diag.patch'; PATCH_NAME='9999-rsd0614-bh25q64-read-profile.patch'; UART_PATCH_NAME='9998-rtl8197f-uart-busy-replay.patch'; UART_DIAG_PATCH_NAME='9998z-rtl8197f-uart-irq-cause-diag.patch'; UART_FIX_PATCH_NAME='9998zz-rtl8197f-uart-register-semantics.patch'
BOOT_MOUNT_ROOT_LINE="\t[ -f /proc/mounts ] || /sbin/mount_root\n"
BOOT_SAFE_LINE="\t# RSD0614 RAM-only bring-up: persistent-root fallback disabled.\n"
DEFAULT_NETWORK_UNSAFE="ucidef_set_interface_lan 'eth0'\n[ -d /sys/class/net/eth1 ] && ucidef_set_interface_wan 'eth1'\n"
DEFAULT_NETWORK_SAFE="# RSD0614 RAM-only bring-up: 02_network + 99-rsd0614-network own eth0.2/eth0.1.\n"
IRQ_UNSAFE_BLOCK="\tic_w32(BIT(15)|BIT(21)|BIT(29), REALTEK_IC_REG_MASK);\n\tic_w32(BIT(15), REALTEK_IC_REG2_MASK);\n\n\t// Return only MARK1\n\treturn BIT(15)|BIT(21)|BIT(29);"
IRQ_SAFE_BLOCK="\t/*\n\t * RSD0614 M3 RAM-boot: clear stale bootloader pending IRQs first.\n\t * PCIe0 (BIT(21)->IP5) is enabled; NET (BIT(15)->IP4) is armed by\n\t * rtl865x_start() on eth0 open; WMAC (BIT(29)->IP6) stays masked until\n\t * rtl8197f_soc_probe() arms it. All three are in mips_chip_irqs so IP2\n\t * ignores them once armed.\n\t */\n\tic_w32(BIT(15)|BIT(21)|BIT(29), REALTEK_IC_REG_STATUS);\n\tic_w32(BIT(21), REALTEK_IC_REG_MASK);\n\tic_w32(BIT(15), REALTEK_IC_REG2_MASK);\n\n\treturn BIT(15)|BIT(21)|BIT(29);"
DISABLE_KERNEL=('CONFIG_RTL8197F_WMAC','CONFIG_RTL8192CD','CONFIG_MTD_SPLIT_FIRMWARE','CONFIG_MTD_SPLIT_CVIMG_FW')
SURVEY_SCRIPT="""#!/bin/sh
# On-demand read-only hardware qualification collector for Rock Space RSD0614 V1.0.
# Never executed automatically at boot. Never writes flash or prints device-unique secrets.
set -eu

print_passive() {
\techo "=== RSD0614_DIAGNOSTIC_MODE ==="
\tif [ -r /etc/rsd0614-diagnostic-mode ]; then
\t\tcat /etc/rsd0614-diagnostic-mode
\tfi
\techo "=== KERNEL_AND_MEMORY ==="
\tuname -a
\tprintf "cmdline="
\tcat /proc/cmdline
\tgrep -E '^(MemTotal|MemFree|MemAvailable):' /proc/meminfo || true
\techo "=== INTERRUPTS ==="
\tcat /proc/interrupts
\techo "=== MTD_SYSFS_GEOMETRY ==="
\tif [ -r /proc/mtd ]; then
\t\tcat /proc/mtd
\tfi
\tfor d in /sys/class/mtd/mtd[0-9]*; do
\t\t[ -d "$d" ] || continue
\t\tb="${d##*/}"
\t\tcase "$b" in
\t\t\t*ro) continue ;;
\t\tesac
\t\tname="$(cat "$d/name" 2>/dev/null || echo unknown)"
\t\tsize="$(cat "$d/size" 2>/dev/null || echo 0)"
\t\tesize="$(cat "$d/erasesize" 2>/dev/null || echo 0)"
\t\tflags="$(cat "$d/flags" 2>/dev/null || echo 0x0)"
\t\twbit=$(( (flags & 0x400) != 0 ? 1 : 0 ))
\t\tcase "$name" in
\t\t\tcfg|cpe|cfm|cfm_backup)
\t\t\t\tpolicy="REDACTED_DEVICE_UNIQUE_NO_RAW_READ"
\t\t\t\t;;
\t\t\t*)
\t\t\t\tpolicy="STRUCTURAL_HEADER_ONLY"
\t\t\t\t;;
\t\tesac
\t\tprintf "%s name=%s size=%s erasesize=%s flags=%s writeable_bit_0x400=%s policy=%s\\n" \\
\t\t\t"$b" "$name" "$size" "$esize" "$flags" "$wbit" "$policy"
\tdone
\techo "=== FLASH_STRUCTURAL_HEADERS_SANITIZED ==="
\tif [ -c /dev/mtd0ro ]; then
\t\tmtd0_hex="$(dd if=/dev/mtd0ro bs=16 count=1 2>/dev/null | hexdump -v -e '16/1 "%02x" "\\n"' || true)"
\t\tprintf "mtd0ro_boot_first16_hex=%s\\n" "${mtd0_hex:-unavailable}"
\telse
\t\techo "mtd0ro_boot_first16_hex=device_absent"
\tfi
\tif [ -c /dev/mtd2ro ]; then
\t\tfw_hex="$(dd if=/dev/mtd2ro bs=16 count=1 2>/dev/null | hexdump -v -e '16/1 "%02x" "\\n"' || true)"
\t\tif [ "${#fw_hex}" -eq 32 ]; then
\t\t\tprintf "%s\\n" "$fw_hex" | awk '{
\t\t\t\th = $0
\t\t\t\tsig_hex = substr(h, 1, 8)
\t\t\t\tsig_ascii = ""
\t\t\t\tok = 1
\t\t\t\thex = "0123456789abcdef"
\t\t\t\tfor (i = 1; i <= 7; i += 2) {
\t\t\t\t\thi = index(hex, tolower(substr(h, i, 1))) - 1
\t\t\t\t\tlo = index(hex, tolower(substr(h, i + 1, 1))) - 1
\t\t\t\t\tv = hi * 16 + lo
\t\t\t\t\tif (hi >= 0 && lo >= 0 && v >= 32 && v <= 126) sig_ascii = sig_ascii sprintf("%c", v)
\t\t\t\t\telse ok = 0
\t\t\t\t}
\t\t\t\tif (!ok) sig_ascii = "non_ascii"
\t\t\t\tprintf "mtd2ro_fw_magic_hex=0x%s mtd2ro_fw_magic_ascii=%s start_addr=0x%s burn_addr=0x%s hdr_len=0x%s\\n", \\
\t\t\t\t\tsig_hex, sig_ascii, substr(h, 9, 8), substr(h, 17, 8), substr(h, 25, 8)
\t\t\t}'
\t\t\tsq_info="$(printf "%s\\n" "$fw_hex" | awk '{
\t\t\t\thex = "0123456789abcdef"
\t\t\t\tlen = 0
\t\t\t\tfor (i = 25; i <= 32; i++) {
\t\t\t\t\tlen = len * 16 + (index(hex, tolower(substr($0, i, 1))) - 1)
\t\t\t\t}
\t\t\t\ttail_off = int((16 + len + 3) / 4) * 4
\t\t\t\tprintf "%d\\n", tail_off
\t\t\t}')"
\t\t\tsq_found="magic=embedded_or_unaligned payload_end_offset=$(printf "0x%x" "$sq_info")"
\t\t\tbase_4k=$(( (sq_info / 4096) * 4096 ))
\t\t\tfor cand in "$sq_info" $(( sq_info + 4 )) "$base_4k" $(( base_4k + 4096 )) $(( base_4k + 8192 )) $(( (sq_info + 65535) / 65536 * 65536 )); do
\t\t\t\t[ "$cand" -gt 0 ] || continue
\t\t\t\tm4="$(dd if=/dev/mtd2ro bs=4 skip=$(( cand / 4 )) count=1 2>/dev/null | hexdump -v -e '4/1 "%02x" "\\n"' || true)"
\t\t\t\tcase "$m4" in
\t\t\t\t\t68737173) sq_found="$(printf "magic=hsqs offset=0x%x" "$cand")"; break ;;
\t\t\t\t\t73717368) sq_found="$(printf "magic=sqsh offset=0x%x" "$cand")"; break ;;
\t\t\t\t\t72366372) sq_found="$(printf "magic=r6cr offset=0x%x" "$cand")"; break ;;
\t\t\t\t\t726f6f74) sq_found="$(printf "magic=root offset=0x%x" "$cand")"; break ;;
\t\t\t\tesac
\t\t\tdone
\t\t\tprintf "mtd2ro_squashfs=%s\\n" "$sq_found"
\t\telse
\t\t\techo "mtd2ro_fw_header=unavailable"
\t\tfi
\telse
\t\techo "mtd2ro_fw_header=device_absent"
\tfi
\techo "sensitive_partitions_redacted=cfg,cpe,cfm,cfm_backup (zero bytes read)"
\techo "=== HW_SURVEY_REGISTERS ==="
\tif [ -r /proc/rsd0614_hw_survey ]; then
\t\tcat /proc/rsd0614_hw_survey
\telse
\t\techo "ERROR: /proc/rsd0614_hw_survey absent"
\tfi
\techo "=== PROBE_STATUS ==="
\tif [ -r /proc/rsd0614_probe ]; then
\t\tcat /proc/rsd0614_probe
\tfi
}

read_gpio_dat() {
\tawk -F= '
\t\t$1 == "GPIO_PABCD_DAT" { a = $2 }
\t\t$1 == "GPIO_PEFGH_DAT" { b = $2 }
\t\tEND { printf "%s %s\\n", (a ? a : "0x00000000"), (b ? b : "0x00000000") }
\t' /proc/rsd0614_hw_survey
}

poll_buttons() {
\tsecs="${1:-10}"
\tcase "$secs" in
\t\t''|*[!0-9]*)
\t\t\techo "Usage: rsd0614-survey buttons [seconds]" >&2
\t\t\texit 2
\t\t\t;;
\tesac
\t[ "$secs" -ge 1 ] && [ "$secs" -le 120 ] || {
\t\techo "seconds must be 1..120" >&2
\t\texit 2
\t}
\t[ -r /proc/rsd0614_hw_survey ] || {
\t\techo "ERROR: /proc/rsd0614_hw_survey not readable" >&2
\t\texit 1
\t}
\tset -- $(read_gpio_dat)
\tprev_a="$1"
\tprev_b="$2"
\tprintf "BUTTON_POLL_START seconds=%s initial_pabcd=%s initial_pefgh=%s\\n" "$secs" "$prev_a" "$prev_b"
\tif sleep 0.2 >/dev/null 2>&1; then
\t\ttotal=$(( secs * 5 ))
\t\tdelay="0.2"
\telse
\t\ttotal="$secs"
\t\tdelay="1"
\tfi
\ti=1
\twhile [ "$i" -le "$total" ]; do
\t\tsleep "$delay"
\t\tset -- $(read_gpio_dat)
\t\tcur_a="$1"
\t\tcur_b="$2"
\t\tif [ "$cur_a" != "$prev_a" ] || [ "$cur_b" != "$prev_b" ]; then
\t\t\txor_a="$(printf "0x%08x" $(( prev_a ^ cur_a )))"
\t\t\txor_b="$(printf "0x%08x" $(( prev_b ^ cur_b )))"
\t\t\tprintf "BUTTON_DELTA sample=%d pabcd=%s->%s(xor=%s) pefgh=%s->%s(xor=%s)\\n" \\
\t\t\t\t"$i" "$prev_a" "$cur_a" "$xor_a" "$prev_b" "$cur_b" "$xor_b"
\t\t\tprev_a="$cur_a"
\t\t\tprev_b="$cur_b"
\t\tfi
\t\ti=$(( i + 1 ))
\tdone
\tprintf "BUTTON_POLL_DONE final_pabcd=%s final_pefgh=%s\\n" "$prev_a" "$prev_b"
}

run_probe() {
\t[ -w /proc/rsd0614_probe ] || {
\t\techo "ERROR: /proc/rsd0614_probe not writable" >&2
\t\texit 1
\t}
\tfor target in "$@"; do
\t\techo "=== TRIGGER_PROBE: $target ==="
\t\tprintf "%s" "$target" > /proc/rsd0614_probe
\tdone
\techo "=== PROBE_RESULTS ==="
\tcat /proc/rsd0614_probe
\techo "=== DMESG_TAIL ==="
\tdmesg | tail -n 25
}

print_backup_guide() {
	cat <<'EOF'
=== RSD0614 READ-ONLY PRIVATE BACKUP GUIDE (FAIL-CLOSED) ===
1. Persistent flash is strictly NO-GO. Never invoke flash erase or write tools.
2. Always read from the kernel read-only character nodes (/dev/mtd<N>ro for N=0..5),
   never writable MTD or mtdblock nodes, after confirming writeable_bit_0x400=0.
3. Because RAM is 64 MiB and full SPI NOR is 8 MiB, NEVER buffer full dumps in /tmp.
   Stream each read-only partition directly over SSH onto your private offline PC
   and verify SHA-256 on both sides:
     for p in 0:bootloader 1:cfg 2:firmware 3:cpe 4:cfm 5:cfm_backup; do
       n=${p%%:*}; name=${p#*:}
       ssh root@192.168.1.1 "dd if=/dev/mtd${n}ro bs=65536 2>/dev/null" > "mtd${n}-${name}.bin"
       rhash=$(ssh root@192.168.1.1 "sha256sum /dev/mtd${n}ro | awk '{print \\$1}'")
       lhash=$(sha256sum "mtd${n}-${name}.bin" | awk '{print $1}')
       echo "mtd${n} (${name}): router=${rhash} local=${lhash}"
     done
     cat mtd0-bootloader.bin mtd1-cfg.bin mtd2-firmware.bin mtd3-cpe.bin mtd4-cfm.bin mtd5-cfm_backup.bin > rsd0614-full-8mb.bin
     sha256sum rsd0614-full-8mb.bin
4. HARD PRIVACY INVARIANT (AGENTS.md):
   NEVER commit, upload, paste, or share full-flash backups or partition dumps of
   cfg (index 1), cpe (index 3), cfm (index 4), or cfm_backup (index 5) — they hold
   device-unique MAC addresses, calibration tables, PINs, PSKs, and credentials.
EOF
}

print_flash_layout() {
	echo "=== FLASH_LAYOUT_READONLY_AUDIT ==="
	echo "policy=STRUCTURAL_HEADERS_ONLY (mtd0ro & mtd2ro only; zero bytes read from cfg/cpe/cfm/cfm_backup)"
	for idx in 0 2; do
		d="/sys/class/mtd/mtd$idx"
		[ -d "$d" ] || { echo "mtd${idx}=sysfs_absent"; continue; }
		name="$(cat "$d/name" 2>/dev/null || echo unknown)"
		size="$(cat "$d/size" 2>/dev/null || echo 0)"
		esize="$(cat "$d/erasesize" 2>/dev/null || echo 0)"
		flags="$(cat "$d/flags" 2>/dev/null || echo 0x0)"
		wbit=$(( (flags & 0x400) != 0 ? 1 : 0 ))
		printf "mtd%s name=%s size=%s erasesize=%s flags=%s writeable_bit_0x400=%s\\n" \\
			"$idx" "$name" "$size" "$esize" "$flags" "$wbit"
	done
	echo "--- mtd0ro bootloader capability tokens ---"
	if [ -c /dev/mtd0ro ]; then
		m0_first="$(dd if=/dev/mtd0ro bs=16 count=1 2>/dev/null | hexdump -v -e '16/1 "%02x" "\\n"' || true)"
		printf "mtd0ro_first16=%s\\n" "${m0_first:-unavailable}"
		tokens="$(dd if=/dev/mtd0ro bs=65536 count=2 2>/dev/null | tr -cd '[:print:]\\n' | grep -Eo 'cr6c|cs6c|r6cr|80a00000|81000000|BH25Q64|RTL8197F-VG|AUTOBURN' | sort -u | tr '\\n' ' ' || true)"
		printf "mtd0ro_tokens=%s\\n" "${tokens:-none}"
	else
		echo "mtd0ro=device_absent"
	fi
	echo "--- mtd2ro stock firmware 64KiB structural map ---"
	if [ -c /dev/mtd2ro ]; then
		m2_size="$(cat /sys/class/mtd/mtd2/size 2>/dev/null || echo 7995392)"
		m2_hdr="$(dd if=/dev/mtd2ro bs=16 count=1 2>/dev/null | hexdump -v -e '16/1 "%02x" "\\n"' || true)"
		printf "mtd2ro_hdr16=%s size=%s\\n" "${m2_hdr:-unavailable}" "$m2_size"
		blocks=$(( m2_size / 65536 ))
		step=0
		non_ff=0
		while [ "$step" -lt "$blocks" ]; do
			m4="$(dd if=/dev/mtd2ro bs=4 skip=$(( step * 16384 )) count=1 2>/dev/null | hexdump -v -e '4/1 "%02x" "\\n"' || true)"
			off=$(( step * 65536 ))
			case "$m4" in
				68737173) printf "block=%03d off=0x%06x magic=hsqs(squashfs-le)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				73717368) printf "block=%03d off=0x%06x magic=sqsh(squashfs-be)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				72366372) printf "block=%03d off=0x%06x magic=r6cr(rtk-rootfs)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				726f6f74) printf "block=%03d off=0x%06x magic=root\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				63723663) printf "block=%03d off=0x%06x magic=cr6c(rtk-kernel)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				63733663) printf "block=%03d off=0x%06x magic=cs6c(rtk-cfg)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				deadc0de) printf "block=%03d off=0x%06x magic=deadc0de(jffs2-eof)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				19852003) printf "block=%03d off=0x%06x magic=19852003(jffs2)\\n" "$step" "$off"; non_ff=$(( non_ff + 1 )) ;;
				ffffffff|"") ;;
				*) non_ff=$(( non_ff + 1 )) ;;
			esac
			step=$(( step + 1 ))
		done
		printf "mtd2ro_blocks_total=%d mtd2ro_blocks_non_ff=%d\\n" "$blocks" "$non_ff"
		if [ "$m2_size" -ge 32 ]; then
			tail32="$(dd if=/dev/mtd2ro bs=32 skip=$(( m2_size / 32 - 1 )) count=1 2>/dev/null | hexdump -v -e '16/1 "%02x" " "' || true)"
			printf "mtd2ro_tail32=%s\\n" "${tail32:-unavailable}"
		fi
	else
		echo "mtd2ro=device_absent"
	fi
}

print_wifi() {
	echo "=== WIFI_MODULE ==="
	grep -E '^rtl8192cd ' /proc/modules 2>/dev/null || echo "rtl8192cd=not_loaded"
	echo "=== PCI_DEVICES ==="
	for p in /sys/bus/pci/devices/*; do
		[ -d "$p" ] || continue
		bn="${p##*/}"
		ven="$(cat "$p/vendor" 2>/dev/null || echo ?)"
		dev="$(cat "$p/device" 2>/dev/null || echo ?)"
		cls="$(cat "$p/class" 2>/dev/null || echo ?)"
		irq="$(cat "$p/irq" 2>/dev/null || echo ?)"
		drv="$(basename "$(readlink "$p/driver" 2>/dev/null || true)" 2>/dev/null || true)"
		[ -n "$drv" ] || drv="none"
		printf "%s vendor=%s device=%s class=%s irq=%s driver=%s\\n" "$bn" "$ven" "$dev" "$cls" "$irq" "$drv"
	done
	echo "=== WIFI_NETDEVS ==="
	for d in /sys/class/net/wlan*; do
		[ -d "$d" ] || continue
		b="${d##*/}"
		addr="$(cat "$d/address" 2>/dev/null || echo unknown)"
		oper="$(cat "$d/operstate" 2>/dev/null || echo unknown)"
		printf "%s state=%s mac=%s\\n" "$b" "$oper" "$addr"
	done
	echo "=== WIFI_CONFIG_AND_LUCI ==="
	ls -ld /etc/Wireless /tmp/Wireless 2>/dev/null || true
	if [ -r /tmp/Wireless/RTL8192CD.dat ]; then
		echo "--- RTL8192CD.dat (sanitized) ---"
		grep -Eiv 'passphrase|psk_key|wepkey|key[0-9]=' /tmp/Wireless/RTL8192CD.dat 2>/dev/null || true
	else
		echo "RTL8192CD.dat=missing"
	fi
	if command -v pgrep >/dev/null 2>&1; then
		pgrep -a uhttpd 2>/dev/null || echo "uhttpd=not_running"
	else
		ps w 2>/dev/null | grep -E '[u]httpd' || echo "uhttpd=not_running"
	fi
	if command -v iwconfig >/dev/null 2>&1; then
		echo "=== IWCONFIG ==="
		iwconfig 2>&1 || true
	fi
	if command -v iwpriv >/dev/null 2>&1; then
		echo "=== IWPRIV_NONSECRET ==="
		for iface in wlan0 wlan1; do
			[ -d "/sys/class/net/$iface" ] || continue
			for mib in channel band phyBandSelect use40M 2ndchoffset block_relay encmode psk_enable; do
				val="$(iwpriv "$iface" get_mib "$mib" 2>/dev/null | sed -E 's/^.*get_mib:[[:space:]]*//' | tr '\\n' ' ' | sed 's/[[:space:]]*$//')"
				[ -n "$val" ] && printf "%s %s=%s\\n" "$iface" "$mib" "$val"
			done
		done
	fi
	echo "=== WIFI_PROC_SUMMARY ==="
	for d in /proc/wlan0 /proc/wlan1; do
		[ -d "$d" ] || continue
		echo "--- $d ---"
		if [ -r "$d/mib_rf" ]; then
			echo "[mib_rf_key_fields]"
			grep -Ei 'rfe_type|pa_type|trswitch|txpwr_lmt|MIMO_TR_mode|dot11channel|phyBandSelect|xcap|tgpwr' "$d/mib_rf" 2>/dev/null || true
		fi
		for f in mib_rf mib_operation sta_info; do
			[ -r "$d/$f" ] || continue
			echo "[$f]"
			grep -Eiv 'passphrase|psk|key|pin|wep|secret' "$d/$f" 2>/dev/null | head -n 55 || true
		done
	done
	if [ -d /sys/kernel/debug/rtl8192cd ]; then
		echo "=== WIFI_DEBUGFS ==="
		for d in /sys/kernel/debug/rtl8192cd/*; do
			[ -d "$d" ] || continue
			echo "--- ${d##*/} ---"
			for f in radio_index rfe_type mac_from_nvmem calibration_len factory_len; do
				[ -r "$d/$f" ] && printf "%s=%s\\n" "$f" "$(cat "$d/$f" 2>/dev/null || true)"
			done
		done
	fi
	echo "=== WIFI_INTERRUPTS ==="
	grep -Ei 'wlan|wifi|rtl8192|pcie|wmac' /proc/interrupts 2>/dev/null || true
	echo "=== WIFI_DMESG ==="
	dmesg | grep -Ei 'rtl8192cd|rtl8197f[-_](wlan|soc)|rtl8197g|8814|realtek-pci|pcie|wlan[01]|CfgFile|board-data|tenda-kv|calibration|rfe_type' | tail -n 80 || true
}

print_net() {
	echo "=== NET_SYSCTL_AND_MEMORY ==="
	grep -E '^(MemTotal|MemFree|MemAvailable|Slab|SReclaimable|SUnreclaim):' /proc/meminfo 2>/dev/null || true
	printf "vm.min_free_kbytes=%s\\n" "$(cat /proc/sys/vm/min_free_kbytes 2>/dev/null || echo unavailable)"
	echo "=== NET_BRIDGE_AND_LINKS ==="
	brctl show 2>/dev/null || true
	ip -4 addr show 2>/dev/null || ifconfig 2>/dev/null || true
	ip link show 2>/dev/null || true
	cat /proc/net/dev 2>/dev/null || true
	brctl showmacs br-lan 2>/dev/null || true
	echo "=== NET_ROUTES_AND_NAT ==="
	ip route 2>/dev/null || true
	iptables -t nat -S 2>/dev/null || true
	echo "=== NET_SWITCH0_SUMMARY ==="
	swconfig dev switch0 show 2>/dev/null | grep -E 'VLAN|ports:|link:|pvid:' || true
	echo "=== NET_LISTENERS ==="
	netstat -lntup 2>/dev/null || netstat -lntu 2>/dev/null || true
	echo "=== NET_FIREWALL_FILTER ==="
	iptables -S 2>/dev/null | head -n 120 || true
	echo "=== INPUT_DEVICES ==="
	cat /proc/bus/input/devices 2>/dev/null || true
	echo "=== NET_WIRELESS_UBUS_SANITIZED ==="
	if command -v ubus >/dev/null 2>&1; then
		ubus call network.wireless status 2>/dev/null | sed -E 's/("key"[[:space:]]*:[[:space:]]*)"[^"]*"/\\1"REDACTED"/g' || true
	fi
	echo "=== NET_ETH_SWITCH_DMESG ==="
	dmesg | grep -Ei 'rtl819x|8367S|switch0|br-lan|eth0|dropbear|uhttpd' | tail -n 60 || true
	echo "=== LOGREAD_TAIL_SANITIZED ==="
	if command -v logread >/dev/null 2>&1; then
		logread 2>/dev/null | grep -Eiv 'passphrase|psk_key|wepkey' | tail -n 60 || true
	fi
}

cmd="${1:-passive}"
case "$cmd" in
	passive|all)
		print_passive
		;;
	buttons)
		shift
		poll_buttons "${1:-10}"
		;;
	probe-smi)
		run_probe smi
		;;
	probe-wmac)
		run_probe wmac
		;;
	probe-pcie0)
		run_probe pcie0
		;;
	probe-all)
		run_probe smi wmac pcie0
		;;
	wifi)
		print_wifi
		;;
	net)
		print_net
		;;
	diag)
		print_net
		print_wifi
		;;
	flash-layout)
		print_flash_layout
		;;
	backup-guide)
		print_backup_guide
		;;
	*)
		echo "Usage: rsd0614-survey {passive|buttons [seconds]|probe-smi|probe-wmac|probe-pcie0|probe-all|wifi|net|diag|flash-layout|backup-guide}" >&2
		exit 2
		;;
esac
"""
BOARD_02_NETWORK="""#!/bin/sh
. /lib/functions.sh
. /lib/functions/uci-defaults.sh

board_config_update
board=$(cat /tmp/sysinfo/board_name 2>/dev/null)

case "$board" in
rockspace,rsd0614)
	# Hardware-verified RTL8367S (cpu_port=6) + SoC CPU-tag VLAN layout:
	# eth0.2 = LAN (VID2, ports 0..3), eth0.1 = WAN (VID1, port 4).
	# Deterministic locally-administered MACs (LAN != WAN; zero device secrets).
	ucidef_set_interfaces_lan_wan "eth0.2" "eth0.1"
	ucidef_add_switch "switch0" "4:wan" "0:lan" "1:lan" "2:lan" "3:lan" "6t@eth0"
	ucidef_set_interface_macaddr "lan" "02:06:14:00:00:01"
	ucidef_set_interface_macaddr "wan" "02:06:14:00:00:02"
	;;
esac

board_config_flush
exit 0
"""
WIFI_NETIFD_SCRIPT="""#!/bin/sh
# Atomic dual-band netifd wireless handler for Rock Space RSD0614 V1.0.
# Drives both wlan0 (PCIe0 RTL8814BR 5 GHz) and wlan1 (on-SoC RTL8197G 2.4 GHz)
# via pinned Realtek SDK v3.6.0 rtl8192cd (WEXT + in-kernel WPA2-PSK).
# Unverified panel LED GPIOs are intentionally never touched.
. /lib/functions.sh
. /lib/netifd/netifd-wireless.sh

# netifd's _wireless_set_brsnoop_isolation injects isolate=1 for bridged APs
# whenever network.lan.multicast_to_unicast is enabled, causing rtl8192cd
# block_relay=1 to drop all same-radio STA-to-STA unicast. Override only this
# implicit injection hook so explicit UCI option isolate remains authoritative.
_wireless_set_brsnoop_isolation() { return 0; }

init_wireless_driver "$@"

IFCONFIG=/sbin/ifconfig
CFGDIR=/tmp/Wireless
CFGFILE="$CFGDIR/RTL8192CD.dat"
LOCKFILE="$CFGDIR/.rtl8192cd.lock"

drv_rtl8192cd_init_device_config() {
	config_add_string path phy hwmode 'macaddr:macaddr'
	config_add_string country
	config_add_int band phy_band
	config_add_int beacon_int dtim_period
	config_add_boolean noscan
}

drv_rtl8192cd_init_iface_config() {
	config_add_string ifname
	config_add_boolean hidden isolate
	config_add_int maxassoc
}

drv_rtl8192cd_cleanup() {
	return 0
}

rtl_htmode_to_use40m() {
	case "$1" in
		VHT80*) echo 2 ;;
		HT40*|VHT40*) echo 1 ;;
		HT20|VHT20|NONE|"") echo 0 ;;
		*) echo 0 ;;
	esac
}

rtl_htmode_to_offset() {
	# Realtek 2ndchoffset MIB: 0=DONT_CARE, 1=LOWER (HT40-), 2=UPPER (HT40+).
	local mode="$1" pband="$2" ch="$3"
	case "$mode" in
		HT40+|VHT40+) echo 2 ;;
		HT40-|VHT40-) echo 1 ;;
		HT40|VHT40)
			if [ "$pband" = "1" ]; then
				case "$ch" in
					1|2|3|4|5|6|7) echo 2 ;;
					8|9|10|11|12|13) echo 1 ;;
					*) echo 0 ;;
				esac
			else
				echo 0
			fi
			;;
		*) echo 0 ;;
	esac
}

rtl_derive_band() {
	local pband="$1" mode="$2"
	if [ "$pband" = "2" ]; then
		case "$mode" in
			VHT*) echo 76 ;;
			HT*) echo 12 ;;
			*) echo 4 ;;
		esac
	else
		case "$mode" in
			HT*|VHT*) echo 11 ;;
			*) echo 3 ;;
		esac
	fi
}

rtl_country_to_regdomain() {
	case "$1" in
		""|US|CA|TW) echo 1 ;;
		EU|DE|GB|FR|VN|CN|SG|AU) echo 3 ;;
		JP) echo 6 ;;
		*[!0-9]*) echo 1 ;;
		*) echo "$1" ;;
	esac
}

rtl_cipher_bits() {
	local cipher="$1" def="$2"
	case "$cipher" in
		ccmp|aes) echo 8 ;;
		tkip) echo 2 ;;
		tkip+ccmp|ccmp+tkip|tkip+aes|aes+tkip) echo 10 ;;
		""|auto) echo "$def" ;;
		*) echo "$def" ;;
	esac
}

rtl_validate_psk() {
	local k="$1"
	local klen="${#k}"
	if [ "$klen" -eq 64 ]; then
		case "$k" in
			*[!0-9a-fA-F]*) return 1 ;;
			*) return 0 ;;
		esac
	fi
	[ "$klen" -ge 8 ] && [ "$klen" -le 63 ]
}

rtl_emit_encryption() {
	local p="$1" enc="$2" key="$3"
	local base="${enc%%+*}"
	local cspec=""
	local cbits encmode

	[ "$base" != "$enc" ] && cspec="${enc#*+}"

	case "$base" in
		none|"")
			echo "${p}_authtype=0"
			echo "${p}_encmode=0"
			echo "${p}_psk_enable=0"
			echo "${p}_wpa_cipher=0"
			echo "${p}_wpa2_cipher=0"
			;;
		psk2)
			rtl_validate_psk "$key" || return 1
			cbits="$(rtl_cipher_bits "$cspec" 8)"
			[ "$cbits" = "2" ] && encmode=2 || encmode=4
			echo "${p}_authtype=0"
			echo "${p}_encmode=$encmode"
			echo "${p}_psk_enable=2"
			echo "${p}_wpa_cipher=0"
			echo "${p}_wpa2_cipher=$cbits"
			printf '%s="%s"\\n' "${p}_passphrase" "$key"
			;;
		psk-mixed|psk+psk2)
			rtl_validate_psk "$key" || return 1
			cbits="$(rtl_cipher_bits "$cspec" 10)"
			[ "$cbits" = "2" ] && encmode=2 || encmode=4
			echo "${p}_authtype=0"
			echo "${p}_encmode=$encmode"
			echo "${p}_psk_enable=3"
			echo "${p}_wpa_cipher=$cbits"
			echo "${p}_wpa2_cipher=$cbits"
			printf '%s="%s"\\n' "${p}_passphrase" "$key"
			;;
		psk)
			rtl_validate_psk "$key" || return 1
			cbits="$(rtl_cipher_bits "$cspec" 2)"
			[ "$cbits" = "2" ] && encmode=2 || encmode=4
			echo "${p}_authtype=0"
			echo "${p}_encmode=$encmode"
			echo "${p}_psk_enable=1"
			echo "${p}_wpa_cipher=$cbits"
			echo "${p}_wpa2_cipher=0"
			printf '%s="%s"\\n' "${p}_passphrase" "$key"
			;;
		*)
			return 1
			;;
	esac
	return 0
}

rtl_merge_fragments() {
	local tmp="$CFGFILE.tmp.$$"
	: > "$tmp"
	for f in "$CFGDIR"/radio_*.dat; do
		[ -f "$f" ] || continue
		cat "$f" >> "$tmp"
	done
	mv -f "$tmp" "$CFGFILE"
}

rtl8192cd_emit_vif() {
	local name="$1"
	local mode ssid encryption key hidden isolate maxassoc ifname
	local existing enc_lines

	json_select config
	json_get_vars mode ssid encryption key hidden isolate maxassoc ifname
	json_select ..

	[ -n "$ifname" ] || ifname="$phy_ifname"

	[ "$mode" = "ap" ] || {
		wireless_setup_vif_failed UNSUPPORTED_MODE
		return 1
	}

	[ -n "$ssid" ] || {
		wireless_setup_vif_failed EMPTY_SSID
		return 1
	}

	[ -d "/sys/class/net/$ifname" ] || {
		wireless_setup_vif_failed NO_VIF_DEVICE
		return 1
	}

	for existing in $_rtl_vifs; do
		if [ "${existing##*:}" = "$ifname" ]; then
			wireless_setup_vif_failed DUPLICATE_IFNAME
			return 1
		fi
	done

	enc_lines="$(rtl_emit_encryption "$ifname" "$encryption" "$key")" || {
		wireless_setup_vif_failed UNSUPPORTED_ENCRYPTION
		return 1
	}

	{
		echo "${ifname}_opmode=16"
		printf '%s="%s"\\n' "${ifname}_ssid" "$ssid"
		echo "${ifname}_hiddenAP=${hidden:-0}"
		echo "${ifname}_block_relay=${isolate:-0}"
		echo "${ifname}_stanum=${maxassoc:-0}"
		printf "%s\\n" "$enc_lines"
	} >> "$FRAGFILE"

	_rtl_vifs="$_rtl_vifs $name:$ifname"
	return 0
}

rtl_find_phy() {
	local want="$1" devname="$2"
	local fallback="wlan0"
	case "$devname" in
		radio[0-9]*) fallback="wlan${devname#radio}" ;;
	esac
	[ -n "$want" ] || want="$fallback"
	[ -d "/sys/class/net/$want" ] && {
		echo "$want"
		return 0
	}
	echo "$want"
}

drv_rtl8192cd_setup() {
	local devname="$1"
	local phy_ifname _rtl_vifs="" FRAGFILE
	local channel htmode country hwmode band phy_band phy macaddr
	local beacon_int dtim_period noscan regdom v

	json_select config
	json_get_vars channel htmode country hwmode band phy_band phy macaddr beacon_int dtim_period noscan
	json_select ..

	phy_ifname="$(rtl_find_phy "$phy" "$devname")"
	[ -d "/sys/class/net/$phy_ifname" ] || {
		wireless_set_retry 0
		wireless_setup_failed NO_DEVICE
		return 1
	}

	case "$channel" in
		""|auto) channel=0 ;;
	esac

	if [ -z "$phy_band" ]; then
		case "$hwmode" in
			11a|a) phy_band=2 ;;
			*)
				if [ "${band:-0}" -ge 64 ] 2>/dev/null || [ "$band" = "4" ] || [ "$band" = "12" ]; then
					phy_band=2
				else
					phy_band=1
				fi
				;;
		esac
	fi
	if [ -z "$band" ]; then
		band="$(rtl_derive_band "$phy_band" "$htmode")"
	fi
	regdom="$(rtl_country_to_regdomain "$country")"
	FRAGFILE="$CFGDIR/radio_${phy_ifname}.dat"

	mkdir -p "$CFGDIR"
	lock "$LOCKFILE"
	[ -L /etc/Wireless ] || [ -e /etc/Wireless ] || ln -s "$CFGDIR" /etc/Wireless
	$IFCONFIG "$phy_ifname" down >/dev/null 2>&1 || true

	{
		echo "${phy_ifname}_band=$band"
		echo "${phy_ifname}_regdomain=$regdom"
		echo "${phy_ifname}_channel=$channel"
		echo "${phy_ifname}_use40M=$(rtl_htmode_to_use40m "$htmode")"
		echo "${phy_ifname}_2ndchoffset=$(rtl_htmode_to_offset "$htmode" "$phy_band" "$channel")"
		echo "${phy_ifname}_bcnint=${beacon_int:-100}"
		echo "${phy_ifname}_dtimperiod=${dtim_period:-1}"
		if [ "${noscan:-0}" = "1" ]; then
			echo "${phy_ifname}_coexist=0"
		else
			echo "${phy_ifname}_coexist=1"
		fi
	} > "$FRAGFILE"

	for_each_interface "ap" rtl8192cd_emit_vif
	if [ -z "$_rtl_vifs" ]; then
		rm -f "$FRAGFILE"
		rtl_merge_fragments
		lock -u "$LOCKFILE"
		wireless_set_retry 0
		wireless_setup_failed NO_VALID_VIF
		return 1
	fi
	rtl_merge_fragments

	if [ -n "$macaddr" ] && ! $IFCONFIG "$phy_ifname" hw ether "$macaddr"; then
		lock -u "$LOCKFILE"
		wireless_setup_failed BAD_MACADDR
		return 1
	fi
	if ! $IFCONFIG "$phy_ifname" up; then
		lock -u "$LOCKFILE"
		wireless_setup_failed IFUP_FAILED
		return 1
	fi
	lock -u "$LOCKFILE"

	for v in $_rtl_vifs; do
		wireless_add_vif "${v%%:*}" "${v##*:}"
	done

	wireless_set_up
}

drv_rtl8192cd_teardown() {
	local devname="$1"
	local phy_ifname phy

	json_select config
	json_get_vars phy
	json_select ..

	phy_ifname="$(rtl_find_phy "$phy" "$devname")"
	mkdir -p "$CFGDIR"
	lock "$LOCKFILE"
	[ -d "/sys/class/net/$phy_ifname" ] && $IFCONFIG "$phy_ifname" down >/dev/null 2>&1 || true
	rm -f "$CFGDIR/radio_${phy_ifname}.dat"
	rtl_merge_fragments
	lock -u "$LOCKFILE"

	return 0
}

add_driver rtl8192cd
"""
UCI_99_NETWORK="""#!/bin/sh
# Configure RTL8367S switch0 VLANs (VID1=WAN port 4, VID2=LAN ports 0..3,
# trunk cpu_port=6 tagged), RAM-boot LAN/WAN interfaces, software flow
# offloading, and M3 dual-band Wi-Fi.
mkdir -p /tmp/Wireless
[ -L /etc/Wireless ] || [ -e /etc/Wireless ] || ln -s /tmp/Wireless /etc/Wireless
[ "$(uci -q get system.@system[0].rsd0614_m3_seeded)" = "1" ] && exit 0

[ -e /etc/config/wireless ] || touch /etc/config/wireless

uci -q batch <<'EOF'
delete network.@switch[0]
delete network.@switch_vlan[0]
delete network.@switch_vlan[0]
add network switch
set network.@switch[-1].name='switch0'
set network.@switch[-1].reset='1'
set network.@switch[-1].enable_vlan='1'
add network switch_vlan
set network.@switch_vlan[-1].device='switch0'
set network.@switch_vlan[-1].vlan='1'
set network.@switch_vlan[-1].vid='1'
set network.@switch_vlan[-1].ports='4 6t'
add network switch_vlan
set network.@switch_vlan[-1].device='switch0'
set network.@switch_vlan[-1].vlan='2'
set network.@switch_vlan[-1].vid='2'
set network.@switch_vlan[-1].ports='0 1 2 3 6t'
set network.lan='interface'
set network.lan.type='bridge'
set network.lan.ifname='eth0.2'
set network.lan.proto='static'
set network.lan.ipaddr='192.168.1.1'
set network.lan.netmask='255.255.255.0'
set network.lan.macaddr='02:06:14:00:00:01'
set network.lan.multicast_to_unicast='0'
set network.wan='interface'
set network.wan.ifname='eth0.1'
set network.wan.proto='dhcp'
set network.wan.macaddr='02:06:14:00:00:02'
commit network
set firewall.@defaults[0].flow_offloading='1'
set firewall.@defaults[0].flow_offloading_hw='0'
commit firewall
set wireless.radio0='wifi-device'
set wireless.radio0.type='rtl8192cd'
set wireless.radio0.phy='wlan0'
set wireless.radio0.hwmode='11a'
set wireless.radio0.channel='36'
set wireless.radio0.htmode='VHT80'
set wireless.radio0.country='US'
set wireless.radio0.disabled='0'
set wireless.default_radio0='wifi-iface'
set wireless.default_radio0.device='radio0'
set wireless.default_radio0.network='lan'
set wireless.default_radio0.mode='ap'
set wireless.default_radio0.ssid='RSD0614-OpenWrt-5G'
set wireless.default_radio0.encryption='psk2'
set wireless.default_radio0.key='rsd0614test'
set wireless.radio1='wifi-device'
set wireless.radio1.type='rtl8192cd'
set wireless.radio1.phy='wlan1'
set wireless.radio1.hwmode='11g'
set wireless.radio1.channel='6'
set wireless.radio1.htmode='HT20'
set wireless.radio1.country='US'
set wireless.radio1.disabled='0'
set wireless.default_radio1='wifi-iface'
set wireless.default_radio1.device='radio1'
set wireless.default_radio1.network='lan'
set wireless.default_radio1.mode='ap'
set wireless.default_radio1.ssid='RSD0614-OpenWrt-2G'
set wireless.default_radio1.encryption='psk2'
set wireless.default_radio1.key='rsd0614test'
commit wireless
set system.@system[0].hostname='RSD0614-OpenWrt'
set system.@system[0].rsd0614_m3_seeded='1'
commit system
EOF
exit 0
"""
INIT_RSD0614_NET="""#!/bin/sh /etc/rc.common
# Rock Space RSD0614 V1.0 M3 wired + dual-band Wi-Fi bring-up helper
# (keeps hardware NAT offload and DIR-842 gw_prog off so L2 aging stays active).
START=97

start() {
	mkdir -p /tmp/Wireless
	[ -L /etc/Wireless ] || [ -e /etc/Wireless ] || ln -s /tmp/Wireless /etc/Wireless
	[ -w /sys/module/rtl819x/parameters/hwnat ] && echo 0 > /sys/module/rtl819x/parameters/hwnat
	[ -w /sys/module/rtl819x/parameters/fabric_gw_rearm ] && echo 0 > /sys/module/rtl819x/parameters/fabric_gw_rearm
	swconfig dev switch0 set apply 1 >/dev/null 2>&1 || true
	logger -t rsd0614-net "RTL8367S switch0 applied; hwnat=0 fabric_gw_rearm=0 lan=$(cat /sys/class/net/eth0.2/address 2>/dev/null || echo none)"
}

stop() {
	[ -w /sys/module/rtl819x/parameters/hwnat ] && echo 0 > /sys/module/rtl819x/parameters/hwnat
}
"""
RC_BUTTON_RESET="""#!/bin/sh
# Rock Space RSD0614 V1.0 RAM-boot safe Reset button handler (&gpio1 4).
# Never invokes overlay/rootfs reset or flash write/erase tools.
# Short accidental taps (<3s) are ignored; holding >=3s reboots cleanly back to stock.
if [ "$ACTION" = "released" ]; then
	if [ "${SEEN:-0}" -ge 3 ]; then
		logger -t rsd0614-reset "Reset button held ${SEEN}s: rebooting RAM-boot session"
		sync
		reboot
	else
		logger -t rsd0614-reset "Ignoring short reset tap (${SEEN:-0}s < 3s)"
	fi
fi
exit 0
"""
BASE_FILES={'etc/rsd0614-diagnostic-mode':'v5.6.4-m3-router-hardened-ramboot\n','etc/sysctl.d/31-rsd0614-lowmem.conf':'vm.min_free_kbytes=2048\n','etc/init.d/done':"#!/bin/sh /etc/rc.common\n# RSD0614 RAM-only bring-up: never discover, mount, format, or switch rootfs_data.\nSTART=95\nboot() {\n\t[ -f /etc/rc.local ] && sh /etc/rc.local\n\t. /etc/diag.sh\n\tset_state done\n}\n",'etc/init.d/rsd0614-net':INIT_RSD0614_NET,'etc/board.d/01_leds':'#!/bin/sh\n# No unverified LED GPIO ownership.\nexit 0\n','etc/board.d/02_network':BOARD_02_NETWORK,'etc/uci-defaults/99-rsd0614-network':UCI_99_NETWORK,'etc/rc.button/reset':RC_BUTTON_RESET,'etc/rc.local':'#!/bin/sh\n# No donor ASIC startup.\nexit 0\n','lib/netifd/wireless/rtl8192cd.sh':WIFI_NETIFD_SCRIPT,'lib/preinit/01_preinit_do_rsd0614_board_detection':'#!/bin/sh\nrsd0614_board_detect() {\n\tmkdir -p /tmp/sysinfo /tmp/Wireless\n\tprintf "%s\\n" "rockspace,rsd0614" > /tmp/sysinfo/board_name\n\tprintf "%s\\n" "Rock Space RSD0614 V1.0" > /tmp/sysinfo/model\n}\nboot_hook_add preinit_main rsd0614_board_detect\n','usr/sbin/rsd0614-survey':SURVEY_SCRIPT}
def patch_image_makefile(text):
    if 'define Device/RSD0614\n' not in text:raise ValueError('RSD0614 device profile must already be installed')
    rows=re.findall(r'^DEVICE_VARS\s*\+=\s*([^\n]*)$',text,re.M)
    if not rows:raise ValueError('Expected DEVICE_VARS declaration is absent')
    if any('DEV_PROFILE' in row.split() for row in rows):return text
    return re.sub(r'^(DEVICE_VARS\s*\+=\s*)([^\n]*)$',lambda m:m[1]+m[2]+' DEV_PROFILE',text,count=1,flags=re.M)
def patch_kernel_config(text):
    keys='|'.join(re.escape(k) for k in DISABLE_KERNEL);pattern=re.compile(rf'^(?:(?:{keys})=.*|# (?:{keys}) is not set)$')
    kept=[line for line in text.splitlines() if not pattern.fullmatch(line)]
    return '\n'.join(kept).rstrip()+'\n'+''.join(f'# {key} is not set\n' for key in DISABLE_KERNEL)
def patch_irq_source(text):
    if IRQ_SAFE_BLOCK in text:return text
    if text.count(IRQ_UNSAFE_BLOCK)!=1:raise ValueError('Unexpected RTL8197F IRQ source; diagnostic mask anchor not unique')
    return text.replace(IRQ_UNSAFE_BLOCK,IRQ_SAFE_BLOCK,1)
def patch_boot_script(text):
    if BOOT_SAFE_LINE in text and BOOT_MOUNT_ROOT_LINE not in text:return text
    if text.count(BOOT_MOUNT_ROOT_LINE)!=1:raise ValueError('Unexpected generic boot script; persistent-root fallback anchor not unique')
    return text.replace(BOOT_MOUNT_ROOT_LINE,BOOT_SAFE_LINE,1)
def patch_default_network_script(text):
    if DEFAULT_NETWORK_SAFE in text and DEFAULT_NETWORK_UNSAFE not in text:return text
    if text.count(DEFAULT_NETWORK_UNSAFE)!=1:raise ValueError('Unexpected default-network script; eth0/eth1 synthesis anchor not unique')
    return text.replace(DEFAULT_NETWORK_UNSAFE,DEFAULT_NETWORK_SAFE,1)
def checked_path(root,relative):
    path=root/relative
    for p in (path,*path.parents):
        if p==root:break
        if p.is_symlink():raise ValueError(f'Refusing symlink in source path: {relative}')
    if root not in path.resolve().parents:raise ValueError('Path containment check failed')
    return path
def tree_records(root):
    records=[]
    for path in sorted(root.rglob('*')):
        rel=path.relative_to(root).as_posix()
        if path.is_symlink():records.append({'path':rel,'symlink':os.readlink(path)})
        elif path.is_file():records.append({'path':rel,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return records
def harden(tree,port,audit,expected=BASE):
    tree=Path(tree).resolve();port=Path(port).resolve();audit=Path(audit).resolve()
    if tree==audit or tree in audit.parents:raise ValueError('Audit backup must be outside OpenWrt source tree')
    head=subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()
    if head!=expected:raise ValueError('Unexpected base revision; no changes made')
    target=checked_path(tree,'target/linux/realtek');old=checked_path(tree,'target/linux/realtek/base-files');mk=checked_path(tree,'target/linux/realtek/image/Makefile');cfg=checked_path(tree,'target/linux/realtek/rtl8197f/config-4.14');irq=checked_path(tree,'target/linux/realtek/files-4.14/arch/mips/realtek/irq.c');boot=checked_path(tree,'package/base-files/files/etc/init.d/boot');defaultnet=checked_path(tree,'package/base-files/files/etc/board.d/99-default_network');vgpatch=checked_path(tree,'target/linux/realtek/patches-4.14/'+VG_RGMII_PCIE_PATCH_NAME);surveypatch=checked_path(tree,'target/linux/realtek/patches-4.14/'+SURVEY_PATCH_NAME);patch=checked_path(tree,'target/linux/realtek/patches-4.14/'+PATCH_NAME);uartpatch=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_PATCH_NAME);uartdiag=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_DIAG_PATCH_NAME);uartfix=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_FIX_PATCH_NAME)
    newmk=patch_image_makefile(mk.read_text());newcfg=patch_kernel_config(cfg.read_text());newirq=patch_irq_source(irq.read_text());newboot=patch_boot_script(boot.read_text());newdefaultnet=patch_default_network_script(defaultnet.read_text());vgpatchdata=(port/'patches'/VG_RGMII_PCIE_PATCH_NAME).read_bytes();surveypatchdata=(port/'patches'/SURVEY_PATCH_NAME).read_bytes();patchdata=(port/'patches'/PATCH_NAME).read_bytes();uartpatchdata=(port/'patches'/UART_PATCH_NAME).read_bytes();uartdiagdata=(port/'patches'/UART_DIAG_PATCH_NAME).read_bytes();uartfixdata=(port/'patches'/UART_FIX_PATCH_NAME).read_bytes()
    if not old.is_dir():raise ValueError('Target userspace tree absent')
    if vgpatch.exists() and vgpatch.read_bytes()!=vgpatchdata:raise ValueError('A different RSD0614 VG RGMII/PCIe patch already exists')
    if surveypatch.exists() and surveypatch.read_bytes()!=surveypatchdata:raise ValueError('A different RSD0614 hardware survey patch already exists')
    if patch.exists() and patch.read_bytes()!=patchdata:raise ValueError('A different BH25Q64 patch already exists')
    if uartpatch.exists() and uartpatch.read_bytes()!=uartpatchdata:raise ValueError('A different RTL8197F UART patch already exists')
    if uartdiag.exists() and uartdiag.read_bytes()!=uartdiagdata:raise ValueError('A different RTL8197F UART diagnostic patch already exists')
    if uartfix.exists() and uartfix.read_bytes()!=uartfixdata:raise ValueError('A different RTL8197F UART register-semantics patch already exists')
    existing=tree_records(old);digest=hashlib.sha256(json.dumps(existing,sort_keys=True).encode()).hexdigest();audit.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.rsd0614-userspace-',dir=target));stage.chmod(0o755)
    try:
        for rel,content in BASE_FILES.items():
            dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content,encoding='utf-8');dest.chmod(0o755 if (content.startswith('#!') or rel.startswith('usr/sbin/')) else 0o644)
        backup=audit/('base-files-'+digest)
        if backup.exists():
            if tree_records(backup)!=existing:raise ValueError('Conflicting retained-source backup')
            shutil.rmtree(old)
        else:old.rename(backup)
        stage.rename(old);mk.write_text(newmk,encoding='utf-8');cfg.write_text(newcfg,encoding='utf-8');irq.write_text(newirq,encoding='utf-8');boot.write_text(newboot,encoding='utf-8');defaultnet.write_text(newdefaultnet,encoding='utf-8');patch.parent.mkdir(parents=True,exist_ok=True);vgpatch.write_bytes(vgpatchdata);surveypatch.write_bytes(surveypatchdata);patch.write_bytes(patchdata);uartpatch.write_bytes(uartpatchdata);uartdiag.write_bytes(uartdiagdata);uartfix.write_bytes(uartfixdata)
        result={'base_commit':head,'retired_target_files':existing,'retained_source_backup':str(backup),'new_target_file_allowlist':sorted(BASE_FILES),'kernel_options_disabled':list(DISABLE_KERNEL),'chip_descriptor':'BH25Q64 / 684017 / normal single-lane reads','vg_rgmii_pcie':'RTL8197FH-VG RGMII pad preservation (0x579fff7f), RTL8367S 1552B trunk max-frame (0x088c=0x0610), CPUICR BUSBURST_128WORDS preservation, USEDDSC>400 threshold, MACCR CF_FCDSC=0x48, PITCR CF_FIX_IPG=1, P0GMIICR RX_delay=7, fabric_gw_rearm=0, PCIe0 40MHz VG MDIO 0x08=0x3101','omnibus_survey':'/proc/rsd0614_hw_survey (0444) + opt-in /proc/rsd0614_probe (0600) + sanitized usr/sbin/rsd0614-survey','direct_device_irqs':'stale pending cleared; PCIe0 BIT(21) enabled; NET BIT(15) armed by rtl865x_start; WMAC BIT(29) kept masked through rtl8197f_soc_probe and unmasked only after request_irq in rtl8192cd_open; BIT(15)|BIT(21)|BIT(29) in mips_chip_irqs','startup_persistent_root':'enabled S10boot/S95done automatic mount_root paths suppressed','default_network':'generic eth0/eth1 synthesis suppressed; RSD0614 02_network + 99-rsd0614-network + rsd0614-net + lib/netifd/wireless/rtl8192cd.sh own switch0/eth0.2/eth0.1 and wlan0/wlan1','uart_register_layout':'Runtime SoC-ID dispatch via realtek,rtl819x-sysc: RTL8197FH-VG (0x81970000) uses standard 16550/DW-APB RBR/THR +0x00 and unmodified LCR/DLL/DLM; non-VG RTL8197F (0x8197F000) retains RX/TX index 9, pre-write composite LCR WLEN translation and raw DLL/DLM callbacks; UPF_SHARE_IRQ|UPF_FIXED_PORT, BUSY replay and bounded IRQ diagnostics preserved','hardware_probe':'NOT YET VERIFIED','ram_boot_authorized':False}
        (audit/'latest-source-isolation.json').write_text(json.dumps(result,indent=2)+'\n');print('SOURCE_ISOLATION: PASS (source mutation only, not a firmware boot test)');print('DEVICE_VARS includes DEV_PROFILE: PASS');print('RSD0614 VG RGMII/PCIe0 patch staged: PASS; target runtime NOT YET VERIFIED');print('RSD0614 omnibus read-only hardware survey patch staged: PASS; target runtime NOT YET VERIFIED');print('BH25Q64 kernel patch staged: PASS; target probe NOT YET VERIFIED');print('RTL8197F BUSY-replay delta staged after base 0004: PASS');print('RTL8197F bounded IRQ-cause diagnostic staged: PASS');print('RTL8197F runtime SoC-ID UART dispatch staged: PASS; hardware validation NOT YET VERIFIED');return result
    finally:
        if stage.exists():shutil.rmtree(stage)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tree',required=True);p.add_argument('--port',required=True);p.add_argument('--audit',required=True);a=p.parse_args()
    try:harden(a.tree,a.port,a.audit)
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit('SOURCE_ISOLATION: FAIL: '+str(e))
