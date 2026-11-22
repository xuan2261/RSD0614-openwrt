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
    sheipasrc=linux/'drivers/spi/spi-sheipa.c';sheipatext=sheipasrc.read_text()
    for token in (
        'spi-sheipa: getdr RFNE timeout',
        'spi-sheipa: spi_flash_wait_busy TIMEOUT',
        'spi-sheipa: flash_wait_busy TIMEOUT',
        'if (clk_div < 28)',
    ):
        if token not in sheipatext:raise ValueError('Hardened bounded spi-sheipa guard missing from compiled source: '+token)
    if 'while (1) {' in sheipatext:raise ValueError('Unbounded polling loop survived in compiled spi-sheipa.c')
    irqsrc=linux/'arch/mips/realtek/irq.c';irqtext=irqsrc.read_text()
    if IRQ_SAFE_BLOCK not in irqtext:raise ValueError('RSD0614 diagnostic direct-IRQ mask hardening missing from compiled source')
    surveysrc=linux/'arch/mips/realtek/rsd0614_survey.c'
    if not surveysrc.is_file():raise ValueError('Missing compiled omnibus survey source: '+str(surveysrc))
    surveytext=surveysrc.read_text()
    for token in (
        'of_machine_is_compatible("rockspace,rsd0614")',
        'proc_create("rsd0614_hw_survey", 0444, NULL, &rsd0614_hw_survey_fops)',
        '.write = NULL,',
        'proc_create("rsd0614_probe", 0600, NULL, &rsd0614_probe_fops)',
        '(sel2 & RSD0614_PINMUX_SMI_MASK) != RSD0614_PINMUX_SMI_GPIO',
        '(cnr & RSD0614_SMI_PIN_MASK) != 0U',
        '"skipped_pinmux_mismatch"',
        'rsd0614_smi_write_reg(0x13C2U, 0x0249U)',
        'orig_64 = sr_r32(REALTEK_SR_WLAN_EN);',
        'sr_w32(orig_64, REALTEK_SR_WLAN_EN);',
        'if ((ltssm & 0x1fU) == 0x11U)',
        'RSD0614_PCIE0_EP_CFG',
        'late_initcall(rsd0614_survey_init);',
    ):
        if token not in surveytext:raise ValueError('RSD0614 omnibus survey/probe guard missing from compiled source: '+token)
    if 'while (1)' in surveytext:raise ValueError('Unbounded while (1) loop found in rsd0614_survey.c')
    if 'smi_write_reg(0x1322' in surveytext:raise ValueError('Forbidden RTL8367 chip reset write found in rsd0614_survey.c')
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
    if not re.search(r'\bunsigned\s+int\s+is_rtl8197f\s*:\s*1\s*;',dwtext):raise ValueError('RTL8197F is_rtl8197f bitfield missing from compiled source')
    for token in (
        'of_device_is_compatible(np, "realtek,rtl8197f-uart")',
        'p->type = PORT_16550A;',
        'p->flags |= UPF_SKIP_TEST | UPF_FIXED_TYPE;',
        'data->skip_autocfg = true;',
        'd->last_lcr = value;',
        'if (d->is_rtl8197f)',
        'writel(d->last_lcr,',
        'data->last_lcr = p->serial_in(p, UART_LCR);'
    ):
        if token not in dwtext:raise ValueError('RTL8197F post-0004/BUSY-replay semantic missing from compiled source: '+token)
    for token in (
        'static void rtl8197f_diag_irq(',
        'if (!d->is_rtl8197f || d->diag_dumped)',
        'd->diag_total == 512',
        'd->diag_msi++',
        'd->diag_thri++',
        'd->diag_rdi++',
        'd->diag_rlsi++',
        'd->diag_busy++',
        'd->diag_timeout++',
        'iir_lsr = p->serial_in(p, UART_IIR);',
        'iir_msr = p->serial_in(p, UART_IIR);',
        'iir_usr = p->serial_in(p, UART_IIR);',
        'iir_rx = p->serial_in(p, UART_IIR);',
        'printk_deferred(KERN_ERR',
        'rtl8197f-uart-diag:'
    ):
        if token not in dwtext:raise ValueError('RTL8197F bounded IRQ-cause diagnostic missing from compiled source: '+token)
    for token in (
        '#include <linux/of_address.h>',
        'static u32 rtl8197f_read_soc_id(void)',
        'of_find_compatible_node(NULL, NULL, "realtek,rtl819x-sysc")',
        'of_iomap(sysc, 0)',
        'iounmap(base)',
        'of_node_put(sysc)',
        'static int rtl8197f_dl_read(struct uart_8250_port *up)',
        'static void rtl8197f_dl_write(struct uart_8250_port *up, int value)',
        'UART_DLL << p->regshift',
        'UART_DLM << p->regshift',
        'static int rtl8197f_translate_lcr(struct dw8250_data *d, int value)',
        'unsigned int wlen = value & UART_LCR_WLEN8;',
        'value = (value & ~UART_LCR_WLEN8) | (wlen - 2);',
        'value = rtl8197f_translate_lcr(d, value);',
        'u32 soc_id = rtl8197f_read_soc_id();',
        'bool is_non_vg = ((soc_id & 0xFFFFF000U) == 0x8197F000U);',
        'data->is_rtl8197f = true;',
        'data->tx_reg = 9;',
        'data->rx_reg = 9;',
        'data->adjlcr = true;',
        'up->dl_read = rtl8197f_dl_read;',
        'up->dl_write = rtl8197f_dl_write;',
        'data->tx_reg = UART_TX;',
        'data->rx_reg = UART_RX;',
        'data->adjlcr = false;',
        'rtl8197f-uart: soc_id=0x%08x mode=%s tx_reg=%u rx_reg=%u adjlcr=%u\\n'
    ):
        if token not in dwtext:raise ValueError('RTL8197F v5.3.9 SoC-ID dispatch semantic missing from compiled source: '+token)
    if dwtext.count('value = rtl8197f_translate_lcr(d, value);')!=3:
        raise ValueError('Expected pre-write rtl8197f_translate_lcr call in all three dw8250_serial_out paths')
    for forbidden,reason in (
        ('p->flags = UPF_SKIP_TEST| UPF_FIXED_TYPE;','Stale RTL8197F p->flags assignment clobbering UPF_SHARE_IRQ|UPF_FIXED_PORT survived compiled source'),
        ('if(value == UART_LCR_WLEN7 || value == UART_LCR_WLEN8)','Stale whole-value RTL8197F LCR adjustment survived compiled source'),
        ('if (!d->adjlcr || d->diag_dumped)','Stale !d->adjlcr IRQ diagnostic guard survived compiled source'),
    ):
        if forbidden in dwtext:raise ValueError(reason)
    text=Path(log).read_text(errors='replace')
    boards=re.findall(r'BOARD="([^"]+)"[^\n]*SUBTARGET="rtl8197f"',text)
    if not boards or any(b!='RSD0614' for b in boards):raise ValueError('Loader BOARD not exclusively RSD0614: '+repr(boards))
    manifest=[]
    for name,rel in [('kernel.config','.config'),('System.map','System.map'),('vmlinux','vmlinux'),('vmlinux-initramfs.elf','../vmlinux-initramfs.elf'),('vmlinux-initramfs.debug','../vmlinux-initramfs.debug'),('spi-nor.c','drivers/mtd/spi-nor/spi-nor.c'),('spi-sheipa.c','drivers/spi/spi-sheipa.c'),('irq.c','arch/mips/realtek/irq.c'),('rsd0614_survey.c','arch/mips/realtek/rsd0614_survey.c'),('serial_reg.h','include/uapi/linux/serial_reg.h'),('8250_dw.c','drivers/tty/serial/8250/8250_dw.c')]:
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
