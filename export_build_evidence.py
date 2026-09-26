#!/usr/bin/env python3
"""Export final kernel evidence and check generated config. No router access."""
from pathlib import Path
import argparse,hashlib,json,re,shutil
from harden_source import DISABLE_KERNEL

def export(tree,out,log):
    tree=Path(tree);out=Path(out);dest=out/'kernel-evidence';dest.mkdir(parents=True,exist_ok=True)
    candidates=list((tree/'build_dir').glob('target-*/linux-realtek_rtl8197f/linux-4.14.187/.config'))
    if len(candidates)!=1:raise ValueError(f'Expected one generated kernel config, found {len(candidates)}')
    linux=candidates[0].parent;config=candidates[0].read_text()
    active=dict(re.findall(r'^(CONFIG_\w+)=(.*)$',config,re.M))
    for key in DISABLE_KERNEL:
        if active.get(key) in ('y','m'):raise ValueError('Unwanted driver/splitter survived config merge: '+key)
    for key in ('CONFIG_MTD_SPI_NOR','CONFIG_SPI_SHEIPA','CONFIG_SOC_RTL8197F'):
        if active.get(key)!='y':raise ValueError('Required kernel feature missing: '+key)
    src=linux/'drivers/mtd/spi-nor/spi-nor.c'
    source=src.read_text()
    if not re.search(r'"bh25q64"\s*,\s*INFO\(0x684017',source):raise ValueError('BH25Q64 patch missing from compiled source')
    text=Path(log).read_text(errors='replace')
    boards=re.findall(r'BOARD="([^"]+)"[^\n]*SUBTARGET="rtl8197f"',text)
    if not boards or any(b!='RSD0614' for b in boards):raise ValueError('Loader BOARD not exclusively RSD0614: '+repr(boards))
    manifest=[]
    for name,rel in [('kernel.config','.config'),('System.map','System.map'),('vmlinux','vmlinux'),('vmlinux-initramfs.elf','../vmlinux-initramfs.elf'),('vmlinux-initramfs.debug','../vmlinux-initramfs.debug'),('spi-nor.c','drivers/mtd/spi-nor/spi-nor.c')]:
        path=linux/rel
        if not path.is_file():raise ValueError('Missing build evidence: '+str(path))
        shutil.copyfile(path,dest/name)
        manifest.append({'name':name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (dest/'manifest.json').write_text(json.dumps({'files':manifest,'loader_board_values':boards},indent=2)+'\n')
    print('GENERATED_KERNEL_CONFIG_AND_SOURCE: PASS; hardware execution remains unverified')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tree');p.add_argument('out');p.add_argument('--log',required=True);a=p.parse_args()
    try:export(a.tree,a.out,a.log)
    except (OSError,ValueError) as e:raise SystemExit('BUILD_EVIDENCE: FAIL: '+str(e))
