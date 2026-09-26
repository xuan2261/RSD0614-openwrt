#!/usr/bin/env python3
"""Isolate the dedicated RSD0614 source tree. Does not contact a router."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
BASE='8a0ccb93f3431bcf8f5c5d03d4acc2c8e442de67'; PATCH_NAME='9999-rsd0614-bh25q64-read-profile.patch'
DISABLE_KERNEL=('CONFIG_NET_RTL819X','CONFIG_RTL8197F_WMAC','CONFIG_RTL8192CD','CONFIG_RTL8366_SMI','CONFIG_RTL8367B_PHY','CONFIG_MTD_SPLIT_FIRMWARE','CONFIG_MTD_SPLIT_CVIMG_FW')
BASE_FILES={'etc/rsd0614-diagnostic-mode':'v5.3-serialdiag\n','etc/board.d/01_leds':'#!/bin/sh\n# No unverified LED GPIO ownership.\nexit 0\n','etc/board.d/02_network':'#!/bin/sh\n# Diagnostic image: no physical network interfaces.\nexit 0\n','etc/config/network':"config interface 'loopback'\n\toption device 'lo'\n\toption ifname 'lo'\n\toption proto 'static'\n\toption ipaddr '127.0.0.1'\n\toption netmask '255.0.0.0'\n",'etc/rc.local':'#!/bin/sh\n# No donor ASIC or Wi-Fi startup.\nexit 0\n','lib/preinit/01_preinit_do_rsd0614_board_detection':'#!/bin/sh\nrsd0614_board_detect() {\n\tmkdir -p /tmp/sysinfo\n\tprintf "%s\\n" "rockspace,rsd0614" > /tmp/sysinfo/board_name\n\tprintf "%s\\n" "Rock Space RSD0614 V1.0" > /tmp/sysinfo/model\n}\nboot_hook_add preinit_main rsd0614_board_detect\n'}
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
    target=checked_path(tree,'target/linux/realtek');old=checked_path(tree,'target/linux/realtek/base-files');mk=checked_path(tree,'target/linux/realtek/image/Makefile');cfg=checked_path(tree,'target/linux/realtek/rtl8197f/config-4.14');patch=checked_path(tree,'target/linux/realtek/patches-4.14/'+PATCH_NAME)
    newmk=patch_image_makefile(mk.read_text());newcfg=patch_kernel_config(cfg.read_text());patchdata=(port/'patches'/PATCH_NAME).read_bytes()
    if not old.is_dir():raise ValueError('Target userspace tree absent')
    if patch.exists() and patch.read_bytes()!=patchdata:raise ValueError('A different BH25Q64 patch already exists')
    existing=tree_records(old);digest=hashlib.sha256(json.dumps(existing,sort_keys=True).encode()).hexdigest();audit.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.rsd0614-userspace-',dir=target));stage.chmod(0o755)
    try:
        for rel,content in BASE_FILES.items():
            dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content,encoding='utf-8');dest.chmod(0o755 if content.startswith('#!') else 0o644)
        backup=audit/('base-files-'+digest)
        if backup.exists():
            if tree_records(backup)!=existing:raise ValueError('Conflicting retained-source backup')
            shutil.rmtree(old)
        else:old.rename(backup)
        stage.rename(old);mk.write_text(newmk,encoding='utf-8');cfg.write_text(newcfg,encoding='utf-8');patch.parent.mkdir(parents=True,exist_ok=True);patch.write_bytes(patchdata)
        result={'base_commit':head,'retired_target_files':existing,'retained_source_backup':str(backup),'new_target_file_allowlist':sorted(BASE_FILES),'kernel_options_disabled':list(DISABLE_KERNEL),'chip_descriptor':'BH25Q64 / 684017 / normal single-lane reads','hardware_probe':'NOT YET VERIFIED','ram_boot_authorized':False}
        (audit/'latest-source-isolation.json').write_text(json.dumps(result,indent=2)+'\n');print('SOURCE_ISOLATION: PASS (source mutation only, not a firmware boot test)');print('DEVICE_VARS includes DEV_PROFILE: PASS');print('BH25Q64 kernel patch staged: PASS; target probe NOT YET VERIFIED');return result
    finally:
        if stage.exists():shutil.rmtree(stage)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tree',required=True);p.add_argument('--port',required=True);p.add_argument('--audit',required=True);a=p.parse_args()
    try:harden(a.tree,a.port,a.audit)
    except (OSError,ValueError,subprocess.SubprocessError) as e:raise SystemExit('SOURCE_ISOLATION: FAIL: '+str(e))
