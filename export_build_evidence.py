#!/usr/bin/env python3
"""Export final kernel evidence and check generated config. No router access."""
from pathlib import Path
import argparse,hashlib,json,re,shutil
from harden_source import DISABLE_KERNEL,IRQ_SAFE_BLOCK

def export(tree,out,log,port_fingerprint='NOT_RECORDED',project_commit='NOT_AVAILABLE',builder_image_id='NOT_RECORDED'):
    tree=Path(tree);out=Path(out);dest=out/'kernel-evidence';dest.mkdir(parents=True,exist_ok=True)
    candidates=list((tree/'build_dir').glob('target-*/linux-realtek_rtl8197f/linux-4.14.187/.config'))
    if len(candidates)!=1:raise ValueError(f'Expected one generated kernel config, found {len(candidates)}')
    linux=candidates[0].parent;config=candidates[0].read_text()
    active=dict(re.findall(r'^(CONFIG_\w+)=(.*)$',config,re.M))
    for key in DISABLE_KERNEL:
        if active.get(key) in ('y','m'):raise ValueError('Unwanted driver/splitter survived config merge: '+key)
    for key in ('CONFIG_MTD_SPI_NOR','CONFIG_SPI_SHEIPA','CONFIG_SOC_RTL8197F','CONFIG_SERIAL_8250','CONFIG_SERIAL_8250_CONSOLE','CONFIG_SERIAL_8250_DW'):
        if active.get(key)!='y':raise ValueError('Required kernel feature missing: '+key)
    src=linux/'drivers/mtd/spi-nor/spi-nor.c'
    source=src.read_text()
    if not re.search(r'"bh25q64"\s*,\s*INFO\(0x684017',source):raise ValueError('BH25Q64 patch missing from compiled source')
    irqsrc=linux/'arch/mips/realtek/irq.c';irqtext=irqsrc.read_text()
    if IRQ_SAFE_BLOCK not in irqtext:raise ValueError('RSD0614 diagnostic direct-IRQ mask hardening missing from compiled source')
    uartsrc=linux/'include/uapi/linux/serial_reg.h';uarttext=uartsrc.read_text()
    uart_required=(
        re.search(r'#define\s+UART_RX\s+0\b',uarttext) and
        re.search(r'#define\s+UART_TX\s+0\b',uarttext) and
        re.search(r'#define\s+UART_LCR_WLEN7\s+0x02\b',uarttext) and
        re.search(r'#define\s+UART_LCR_WLEN8\s+0x03\b',uarttext) and
        re.search(r'#define\s+UART_IIR_ID\s+0x0e\b',uarttext)
    )
    if not uart_required:raise ValueError('Generic serial_reg.h was unexpectedly changed; RTL8197F mapping must stay in post-0004 DW8250 source')
    dwsrc=linux/'drivers/tty/serial/8250/8250_dw.c';dwtext=dwsrc.read_text()
    if not re.search(r'\bu8\s+last_lcr\s*;',dwtext):raise ValueError('RTL8197F BUSY-replay last_lcr field missing from compiled source')
    for token in (
        'of_device_is_compatible(np, "realtek,rtl8197f-uart")',
        'data->tx_reg = 9;',
        'data->rx_reg = 9;',
        'data->adjlcr=true;',
        'value -= 2;',
        'p->type = PORT_16550A;',
        'data->skip_autocfg = true;',
        'd->last_lcr = value;',
        'writel(d->last_lcr,',
        'data->last_lcr = p->serial_in(p, UART_LCR);'
    ):
        if token not in dwtext:raise ValueError('RTL8197F post-0004/BUSY-replay semantic missing from compiled source: '+token)
    text=Path(log).read_text(errors='replace')
    boards=re.findall(r'BOARD="([^"]+)"[^\n]*SUBTARGET="rtl8197f"',text)
    if not boards or any(b!='RSD0614' for b in boards):raise ValueError('Loader BOARD not exclusively RSD0614: '+repr(boards))
    manifest=[]
    for name,rel in [('kernel.config','.config'),('System.map','System.map'),('vmlinux','vmlinux'),('vmlinux-initramfs.elf','../vmlinux-initramfs.elf'),('vmlinux-initramfs.debug','../vmlinux-initramfs.debug'),('spi-nor.c','drivers/mtd/spi-nor/spi-nor.c'),('irq.c','arch/mips/realtek/irq.c'),('serial_reg.h','include/uapi/linux/serial_reg.h'),('8250_dw.c','drivers/tty/serial/8250/8250_dw.c')]:
        path=linux/rel
        if not path.is_file():raise ValueError('Missing build evidence: '+str(path))
        shutil.copyfile(path,dest/name)
        manifest.append({'name':name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    provenance={'port_input_fingerprint':port_fingerprint,'project_commit':project_commit,'builder_image_id':builder_image_id}
    (dest/'manifest.json').write_text(json.dumps({'files':manifest,'loader_board_values':boards,'provenance':provenance},indent=2)+'\n')
    print('GENERATED_KERNEL_CONFIG_AND_SOURCE: PASS; hardware execution remains unverified')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tree');p.add_argument('out');p.add_argument('--log',required=True);p.add_argument('--port-fingerprint',default='NOT_RECORDED');p.add_argument('--project-commit',default='NOT_AVAILABLE');p.add_argument('--builder-image-id',default='NOT_RECORDED');a=p.parse_args()
    try:export(a.tree,a.out,a.log,port_fingerprint=a.port_fingerprint,project_commit=a.project_commit,builder_image_id=a.builder_image_id)
    except (OSError,ValueError) as e:raise SystemExit('BUILD_EVIDENCE: FAIL: '+str(e))
