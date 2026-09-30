#!/usr/bin/env python3
"""Isolate the dedicated RSD0614 source tree. Does not contact a router."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
BASE='8a0ccb93f3431bcf8f5c5d03d4acc2c8e442de67'; PATCH_NAME='9999-rsd0614-bh25q64-read-profile.patch'; UART_PATCH_NAME='9998-rtl8197f-uart-busy-replay.patch'; UART_DIAG_PATCH_NAME='9998z-rtl8197f-uart-irq-cause-diag.patch'
BOOT_MOUNT_ROOT_LINE="\t[ -f /proc/mounts ] || /sbin/mount_root\n"
BOOT_SAFE_LINE="\t# RSD0614 RAM-only diagnostic: persistent-root fallback disabled.\n"
DEFAULT_NETWORK_UNSAFE="ucidef_set_interface_lan 'eth0'\n[ -d /sys/class/net/eth1 ] && ucidef_set_interface_wan 'eth1'\n"
DEFAULT_NETWORK_SAFE="# RSD0614 RAM-only diagnostic: do not synthesize physical interfaces.\n"
IRQ_UNSAFE_BLOCK="\tic_w32(BIT(15)|BIT(21)|BIT(29), REALTEK_IC_REG_MASK);\n\tic_w32(BIT(15), REALTEK_IC_REG2_MASK);\n\n\t// Return only MARK1\n\treturn BIT(15)|BIT(21)|BIT(29);"
IRQ_SAFE_BLOCK="\t/*\n\t * RSD0614 serial-only diagnostic: the bootloader has just used\n\t * Ethernet for TFTP, while NET/PCIe/WMAC drivers are deliberately\n\t * disabled. Clear and keep their direct interrupt sources masked so\n\t * stale bootloader state cannot create an unowned interrupt storm.\n\t */\n\tic_w32(BIT(15)|BIT(21)|BIT(29), REALTEK_IC_REG_STATUS);\n\tic_w32(0, REALTEK_IC_REG_MASK);\n\tic_w32(BIT(15), REALTEK_IC_REG2_MASK);\n\n\treturn 0;"
DISABLE_KERNEL=('CONFIG_NET_RTL819X','CONFIG_RTL8197F_WMAC','CONFIG_RTL8192CD','CONFIG_RTL8366_SMI','CONFIG_RTL8367B_PHY','CONFIG_MTD_SPLIT_FIRMWARE','CONFIG_MTD_SPLIT_CVIMG_FW')
BASE_FILES={'etc/rsd0614-diagnostic-mode':'v5.3.7-uart-irq-cause\n','etc/init.d/done':"#!/bin/sh /etc/rc.common\n# RSD0614 RAM-only diagnostic: never discover, mount, format, or switch rootfs_data.\nSTART=95\nboot() {\n\t[ -f /etc/rc.local ] && sh /etc/rc.local\n\t. /etc/diag.sh\n\tset_state done\n}\n",'etc/board.d/01_leds':'#!/bin/sh\n# No unverified LED GPIO ownership.\nexit 0\n','etc/board.d/02_network':'#!/bin/sh\n# Diagnostic image: no physical network interfaces.\nexit 0\n','etc/config/network':"config interface 'loopback'\n\toption device 'lo'\n\toption ifname 'lo'\n\toption proto 'static'\n\toption ipaddr '127.0.0.1'\n\toption netmask '255.0.0.0'\n",'etc/rc.local':'#!/bin/sh\n# No donor ASIC or Wi-Fi startup.\nexit 0\n','lib/preinit/01_preinit_do_rsd0614_board_detection':'#!/bin/sh\nrsd0614_board_detect() {\n\tmkdir -p /tmp/sysinfo\n\tprintf "%s\\n" "rockspace,rsd0614" > /tmp/sysinfo/board_name\n\tprintf "%s\\n" "Rock Space RSD0614 V1.0" > /tmp/sysinfo/model\n}\nboot_hook_add preinit_main rsd0614_board_detect\n'}
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
    target=checked_path(tree,'target/linux/realtek');old=checked_path(tree,'target/linux/realtek/base-files');mk=checked_path(tree,'target/linux/realtek/image/Makefile');cfg=checked_path(tree,'target/linux/realtek/rtl8197f/config-4.14');irq=checked_path(tree,'target/linux/realtek/files-4.14/arch/mips/realtek/irq.c');boot=checked_path(tree,'package/base-files/files/etc/init.d/boot');defaultnet=checked_path(tree,'package/base-files/files/etc/board.d/99-default_network');patch=checked_path(tree,'target/linux/realtek/patches-4.14/'+PATCH_NAME);uartpatch=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_PATCH_NAME);uartdiag=checked_path(tree,'target/linux/realtek/patches-4.14/'+UART_DIAG_PATCH_NAME)
    newmk=patch_image_makefile(mk.read_text());newcfg=patch_kernel_config(cfg.read_text());newirq=patch_irq_source(irq.read_text());newboot=patch_boot_script(boot.read_text());newdefaultnet=patch_default_network_script(defaultnet.read_text());patchdata=(port/'patches'/PATCH_NAME).read_bytes();uartpatchdata=(port/'patches'/UART_PATCH_NAME).read_bytes();uartdiagdata=(port/'patches'/UART_DIAG_PATCH_NAME).read_bytes()
    if not old.is_dir():raise ValueError('Target userspace tree absent')
    if patch.exists() and patch.read_bytes()!=patchdata:raise ValueError('A different BH25Q64 patch already exists')
    if uartpatch.exists() and uartpatch.read_bytes()!=uartpatchdata:raise ValueError('A different RTL8197F UART patch already exists')
    if uartdiag.exists() and uartdiag.read_bytes()!=uartdiagdata:raise ValueError('A different RTL8197F UART diagnostic patch already exists')
    existing=tree_records(old);digest=hashlib.sha256(json.dumps(existing,sort_keys=True).encode()).hexdigest();audit.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.rsd0614-userspace-',dir=target));stage.chmod(0o755)
    try:
        for rel,content in BASE_FILES.items():
            dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content,encoding='utf-8');dest.chmod(0o755 if content.startswith('#!') else 0o644)
        backup=audit/('base-files-'+digest)
        if backup.exists():
            if tree_records(backup)!=existing:raise ValueError('Conflicting retained-source backup')
            shutil.rmtree(old)
        else:old.rename(backup)
        stage.rename(old);mk.write_text(newmk,encoding='utf-8');cfg.write_text(newcfg,encoding='utf-8');irq.write_text(newirq,encoding='utf-8');boot.write_text(newboot,encoding='utf-8');defaultnet.write_text(newdefaultnet,encoding='utf-8');patch.parent.mkdir(parents=True,exist_ok=True);patch.write_bytes(patchdata);uartpatch.write_bytes(uartpatchdata);uartdiag.write_bytes(uartdiagdata)
        result={'base_commit':head,'retired_target_files':existing,'retained_source_backup':str(backup),'new_target_file_allowlist':sorted(BASE_FILES),'kernel_options_disabled':list(DISABLE_KERNEL),'chip_descriptor':'BH25Q64 / 684017 / normal single-lane reads','direct_device_irqs':'NET/PCIe/WiFi pending cleared and masked','startup_persistent_root':'enabled S10boot/S95done automatic mount_root paths suppressed','default_network':'eth0/eth1 synthesis suppressed','uart_register_layout':'OpenWrt 0004 supplies RTL8197F tx/rx index 9 and adjlcr; v5.3.6 BUSY replay retained; v5.3.7 adds bounded IIR cause instrumentation at pass 512','hardware_probe':'NOT YET VERIFIED','ram_boot_authorized':False}
        (audit/'latest-source-isolation.json').write_text(json.dumps(result,indent=2)+'\n');print('SOURCE_ISOLATION: PASS (source mutation only, not a firmware boot test)');print('DEVICE_VARS includes DEV_PROFILE: PASS');print('BH25Q64 kernel patch staged: PASS; target probe NOT YET VERIFIED');print('RTL8197F BUSY-replay delta staged after base 0004: PASS');print('RTL8197F bounded IRQ-cause diagnostic staged: PASS; hardware cause NOT YET VERIFIED');return result
    finally:
        if stage.exists():shutil.rmtree(stage)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tree',required=True);p.add_argument('--port',required=True);p.add_argument('--audit',required=True);a=p.parse_args()
    try:harden(a.tree,a.port,a.audit)
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit('SOURCE_ISOLATION: FAIL: '+str(e))
