#!/usr/bin/env python3
"""Isolate the dedicated RSD0614 source tree. Does not contact a router."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
BASE='8a0ccb93f3431bcf8f5c5d03d4acc2c8e442de67'; SURVEY_PATCH_NAME='9997-rsd0614-hw-survey-diag.patch'; PATCH_NAME='9999-rsd0614-bh25q64-read-profile.patch'; UART_PATCH_NAME='9998-rtl8197f-uart-busy-replay.patch'; UART_DIAG_PATCH_NAME='9998z-rtl8197f-uart-irq-cause-diag.patch'; UART_FIX_PATCH_NAME='9998zz-rtl8197f-uart-register-semantics.patch'
BOOT_MOUNT_ROOT_LINE="\t[ -f /proc/mounts ] || /sbin/mount_root\n"
BOOT_SAFE_LINE="\t# RSD0614 RAM-only diagnostic: persistent-root fallback disabled.\n"
DEFAULT_NETWORK_UNSAFE="ucidef_set_interface_lan 'eth0'\n[ -d /sys/class/net/eth1 ] && ucidef_set_interface_wan 'eth1'\n"
DEFAULT_NETWORK_SAFE="# RSD0614 RAM-only diagnostic: do not synthesize physical interfaces.\n"
IRQ_UNSAFE_BLOCK="\tic_w32(BIT(15)|BIT(21)|BIT(29), REALTEK_IC_REG_MASK);\n\tic_w32(BIT(15), REALTEK_IC_REG2_MASK);\n\n\t// Return only MARK1\n\treturn BIT(15)|BIT(21)|BIT(29);"
IRQ_SAFE_BLOCK="\t/*\n\t * RSD0614 serial-only diagnostic: the bootloader has just used\n\t * Ethernet for TFTP, while NET/PCIe/WMAC drivers are deliberately\n\t * disabled. Clear and keep their direct interrupt sources masked so\n\t * stale bootloader state cannot create an unowned interrupt storm.\n\t */\n\tic_w32(BIT(15)|BIT(21)|BIT(29), REALTEK_IC_REG_STATUS);\n\tic_w32(0, REALTEK_IC_REG_MASK);\n\tic_w32(BIT(15), REALTEK_IC_REG2_MASK);\n\n\treturn 0;"
DISABLE_KERNEL=('CONFIG_NET_RTL819X','CONFIG_RTL8197F_WMAC','CONFIG_RTL8192CD','CONFIG_RTL8366_SMI','CONFIG_RTL8367B_PHY','CONFIG_MTD_SPLIT_FIRMWARE','CONFIG_MTD_SPLIT_CVIMG_FW')
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
\tcat <<'EOF'
=== RSD0614 READ-ONLY PRIVATE BACKUP GUIDE (FAIL-CLOSED) ===
1. Persistent flash is strictly NO-GO. Never invoke flash erase or write tools.
2. Always read from the kernel read-only character nodes (/dev/mtd<N>ro for N=0..5),
   never writable MTD or mtdblock nodes, after confirming writeable_bit_0x400=0.
3. Because RAM is 64 MiB and full SPI NOR is 8 MiB, stream or copy one read-only
   partition at a time into /tmp (tmpfs in RAM), hash it with sha256sum, transfer
   it privately to your offline workstation, and delete the /tmp copy before the next.
4. HARD PRIVACY INVARIANT (AGENTS.md):
   NEVER commit, upload, paste, or share full-flash backups or partition dumps of
   cfg (index 1), cpe (index 3), cfm (index 4), or cfm_backup (index 5) — they hold
   device-unique MAC addresses, calibration tables, PINs, PSKs, and credentials.
EOF
}

cmd="${1:-passive}"
case "$cmd" in
\tpassive|all)
\t\tprint_passive
\t\t;;
\tbuttons)
\t\tshift
\t\tpoll_buttons "${1:-10}"
\t\t;;
\tprobe-smi)
\t\trun_probe smi
\t\t;;
\tprobe-wmac)
\t\trun_probe wmac
\t\t;;
\tprobe-pcie0)
\t\trun_probe pcie0
\t\t;;
\tprobe-all)
\t\trun_probe smi wmac pcie0
\t\t;;
\tbackup-guide)
\t\tprint_backup_guide
\t\t;;
\t*)
\t\techo "Usage: rsd0614-survey {passive|buttons [seconds]|probe-smi|probe-wmac|probe-pcie0|probe-all|backup-guide}" >&2
\t\texit 2
\t\t;;
esac
"""
BASE_FILES={'etc/rsd0614-diagnostic-mode':'v5.4.2-omnibus-readonly-survey\n','etc/init.d/done':"#!/bin/sh /etc/rc.common\n# RSD0614 RAM-only diagnostic: never discover, mount, format, or switch rootfs_data.\nSTART=95\nboot() {\n\t[ -f /etc/rc.local ] && sh /etc/rc.local\n\t. /etc/diag.sh\n\tset_state done\n}\n",'etc/board.d/01_leds':'#!/bin/sh\n# No unverified LED GPIO ownership.\nexit 0\n','etc/board.d/02_network':'#!/bin/sh\n# Diagnostic image: no physical network interfaces.\nexit 0\n','etc/config/network':"config interface 'loopback'\n\toption device 'lo'\n\toption ifname 'lo'\n\toption proto 'static'\n\toption ipaddr '127.0.0.1'\n\toption netmask '255.0.0.0'\n",'etc/rc.local':'#!/bin/sh\n# No donor ASIC or Wi-Fi startup.\nexit 0\n','lib/preinit/01_preinit_do_rsd0614_board_detection':'#!/bin/sh\nrsd0614_board_detect() {\n\tmkdir -p /tmp/sysinfo\n\tprintf "%s\\n" "rockspace,rsd0614" > /tmp/sysinfo/board_name\n\tprintf "%s\\n" "Rock Space RSD0614 V1.0" > /tmp/sysinfo/model\n}\nboot_hook_add preinit_main rsd0614_board_detect\n','usr/sbin/rsd0614-survey':SURVEY_SCRIPT}
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
    target=checked_path(tree,'target/linux/realtek');old=checked_path(tree,'target/linux/realtek/base-files');mk=checked_path(tree,'target/linux/realtek/image/Makefile');cfg=checked_path(tree,'target/linux/realtek/rtl8197f/config-4.14');irq=checked_path(tree,'target/linux/realtek/files-4.14/arch/mips/realtek/irq.c');boot=checked_path(tree,'package/base-files/files/etc/init.d/boot');defaultnet=checked_path(tree,'package/base-files/files/etc/board.d/99-default_network');surveypatch=checked_path(tree,'target/linux/realtek/patches-4.14/'+SURVEY_PATCH_NAME);patch=checked_path(tree,'target/linux/realtek/patches-4.14/'+PATCH_NAME);uartpatch=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_PATCH_NAME);uartdiag=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_DIAG_PATCH_NAME);uartfix=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_FIX_PATCH_NAME)
    newmk=patch_image_makefile(mk.read_text());newcfg=patch_kernel_config(cfg.read_text());newirq=patch_irq_source(irq.read_text());newboot=patch_boot_script(boot.read_text());newdefaultnet=patch_default_network_script(defaultnet.read_text());surveypatchdata=(port/'patches'/SURVEY_PATCH_NAME).read_bytes();patchdata=(port/'patches'/PATCH_NAME).read_bytes();uartpatchdata=(port/'patches'/UART_PATCH_NAME).read_bytes();uartdiagdata=(port/'patches'/UART_DIAG_PATCH_NAME).read_bytes();uartfixdata=(port/'patches'/UART_FIX_PATCH_NAME).read_bytes()
    if not old.is_dir():raise ValueError('Target userspace tree absent')
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
        stage.rename(old);mk.write_text(newmk,encoding='utf-8');cfg.write_text(newcfg,encoding='utf-8');irq.write_text(newirq,encoding='utf-8');boot.write_text(newboot,encoding='utf-8');defaultnet.write_text(newdefaultnet,encoding='utf-8');patch.parent.mkdir(parents=True,exist_ok=True);surveypatch.write_bytes(surveypatchdata);patch.write_bytes(patchdata);uartpatch.write_bytes(uartpatchdata);uartdiag.write_bytes(uartdiagdata);uartfix.write_bytes(uartfixdata)
        result={'base_commit':head,'retired_target_files':existing,'retained_source_backup':str(backup),'new_target_file_allowlist':sorted(BASE_FILES),'kernel_options_disabled':list(DISABLE_KERNEL),'chip_descriptor':'BH25Q64 / 684017 / normal single-lane reads','omnibus_survey':'/proc/rsd0614_hw_survey (0444) + opt-in /proc/rsd0614_probe (0600) + sanitized usr/sbin/rsd0614-survey','direct_device_irqs':'NET/PCIe/WiFi pending cleared and masked','startup_persistent_root':'enabled S10boot/S95done automatic mount_root paths suppressed','default_network':'eth0/eth1 synthesis suppressed','uart_register_layout':'Runtime SoC-ID dispatch via realtek,rtl819x-sysc: RTL8197FH-VG (0x81970000) uses standard 16550/DW-APB RBR/THR +0x00 and unmodified LCR/DLL/DLM; non-VG RTL8197F (0x8197F000) retains RX/TX index 9, pre-write composite LCR WLEN translation and raw DLL/DLM callbacks; UPF_SHARE_IRQ|UPF_FIXED_PORT, BUSY replay and bounded IRQ diagnostics preserved','hardware_probe':'NOT YET VERIFIED','ram_boot_authorized':False}
        (audit/'latest-source-isolation.json').write_text(json.dumps(result,indent=2)+'\n');print('SOURCE_ISOLATION: PASS (source mutation only, not a firmware boot test)');print('DEVICE_VARS includes DEV_PROFILE: PASS');print('RSD0614 omnibus read-only hardware survey patch staged: PASS; target runtime NOT YET VERIFIED');print('BH25Q64 kernel patch staged: PASS; target probe NOT YET VERIFIED');print('RTL8197F BUSY-replay delta staged after base 0004: PASS');print('RTL8197F bounded IRQ-cause diagnostic staged: PASS');print('RTL8197F runtime SoC-ID UART dispatch staged: PASS; hardware validation NOT YET VERIFIED');return result
    finally:
        if stage.exists():shutil.rmtree(stage)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tree',required=True);p.add_argument('--port',required=True);p.add_argument('--audit',required=True);a=p.parse_args()
    try:harden(a.tree,a.port,a.audit)
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit('SOURCE_ISOLATION: FAIL: '+str(e))
