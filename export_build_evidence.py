#!/usr/bin/env python3
"""Export final kernel evidence and check generated config. No router access."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,struct
from harden_source import DISABLE_KERNEL,IRQ_SAFE_BLOCK

def parse_elf32_le_kmod_info(data):
    """Parse an ELF32 little-endian MIPS relocatable .ko and extract undef symbols, .modinfo, and .bss size."""
    if len(data)<52 or data[:4]!=b'\x7fELF':
        raise ValueError('rtl8192cd.ko is not a valid ELF file')
    if data[4]!=1 or data[5]!=1:
        raise ValueError('rtl8192cd.ko is not ELF32 little-endian')
    e_type,e_machine,_,_,_,e_shoff,_,_,_,_,e_shentsize,e_shnum,e_shstrndx=struct.unpack_from('<HHIIIIIHHHHHH',data,16)
    if e_type!=1 or e_machine!=8:
        raise ValueError(f'rtl8192cd.ko unexpected ELF type/machine: {e_type}/{e_machine}')
    if e_shoff==0 or e_shentsize<40 or e_shnum==0 or e_shoff+e_shentsize*e_shnum>len(data):
        raise ValueError('rtl8192cd.ko has invalid ELF section header table')
    secs=[struct.unpack_from('<10I',data,e_shoff+i*e_shentsize) for i in range(e_shnum)]
    if e_shstrndx>=len(secs):
        raise ValueError('rtl8192cd.ko has invalid e_shstrndx')
    shstr_off,shstr_sz=secs[e_shstrndx][4],secs[e_shstrndx][5]
    if shstr_off+shstr_sz>len(data):
        raise ValueError('rtl8192cd.ko .shstrtab out of bounds')
    shstr=data[shstr_off:shstr_off+shstr_sz]
    def cstr(buf,off):
        if off>=len(buf):raise ValueError('ELF string offset out of bounds')
        z=buf.find(b'\x00',off)
        return buf[off:z] if z>=0 else buf[off:]
    undef_global=set();defined_global=set();modinfo=b'';bss_bytes=0;saw_symtab=False
    for sh_name,sh_type,_sh_flags,_sh_addr,sh_off,sh_size,sh_link,_sh_info,_sh_align,sh_entsize in secs:
        sname=cstr(shstr,sh_name)
        if sh_type!=8 and sh_off+sh_size>len(data):
            raise ValueError('ELF section exceeds file bounds: '+sname.decode('ascii','replace'))
        if sname==b'.modinfo':
            modinfo=data[sh_off:sh_off+sh_size]
        elif sname==b'.bss':
            bss_bytes=sh_size
        if sh_type==2:
            saw_symtab=True
            if sh_link>=len(secs) or sh_entsize<16 or (sh_size%sh_entsize)!=0:
                raise ValueError('Invalid ELF SHT_SYMTAB section')
            str_off,str_sz=secs[sh_link][4],secs[sh_link][5]
            if str_off+str_sz>len(data):
                raise ValueError('Invalid ELF SHT_STRTAB bounds')
            strtab=data[str_off:str_off+str_sz]
            for off in range(sh_off,sh_off+sh_size,sh_entsize):
                st_name,_st_val,_st_sz,st_info,_st_other,st_shndx=struct.unpack_from('<IIIBBH',data,off)
                bind=st_info>>4
                if st_name!=0 and bind==1:
                    sym=cstr(strtab,st_name).decode('ascii')
                    if st_shndx==0:
                        undef_global.add(sym)
                    else:
                        defined_global.add(sym)
    if not saw_symtab:
        raise ValueError('rtl8192cd.ko missing SHT_SYMTAB section')
    modinfo_entries=[x.decode('ascii','replace') for x in modinfo.split(b'\x00') if x]
    if not any(x.startswith('license=GPL') for x in modinfo_entries):
        raise ValueError('rtl8192cd.ko missing GPL license in .modinfo')
    return {'undef_symbols':sorted(undef_global),'defined_symbols':sorted(defined_global),'modinfo':modinfo_entries,'bss_bytes':bss_bytes}

def parse_system_map_ksymtab(text):
    return set(re.findall(r'^[0-9a-fA-F]+\s+[rRdD]\s+__ksymtab_(\S+)$',text,re.M))

def export(tree,out,log,port_fingerprint='NOT_RECORDED',project_commit='NOT_AVAILABLE',builder_image_id='NOT_RECORDED'):
    tree=Path(tree);out=Path(out);dest=out/'kernel-evidence';dest.mkdir(parents=True,exist_ok=True)
    candidates=list((tree/'build_dir').glob('target-*/linux-realtek_rtl8197f/linux-4.14.187/.config'))
    if len(candidates)!=1:raise ValueError(f'Expected one generated kernel config, found {len(candidates)}')
    linux=candidates[0].parent;config=candidates[0].read_text()
    active=dict(re.findall(r'^(CONFIG_\w+)=(.*)$',config,re.M))
    for key in DISABLE_KERNEL:
        if active.get(key) in ('y','m'):raise ValueError('Unwanted driver/splitter survived config merge: '+key)
    for key in ('CONFIG_MTD_SPI_NOR','CONFIG_SPI_SHEIPA','CONFIG_SOC_RTL8197F','CONFIG_SERIAL_8250','CONFIG_SERIAL_8250_CONSOLE','CONFIG_SERIAL_8250_DW','CONFIG_NET_RTL819X','CONFIG_RTL8366_SMI','CONFIG_RTL8367B_PHY','CONFIG_PCI','CONFIG_WIRELESS','CONFIG_WIRELESS_EXT'):
        if active.get(key)!='y':raise ValueError('Required kernel feature missing: '+key)
    ethsrc=linux/'drivers/net/ethernet/rtl819x/rtl819x-eth.c'
    if not ethsrc.is_file():raise ValueError('Missing compiled rtl819x-eth.c: '+str(ethsrc))
    ethtext=ethsrc.read_text()
    for token in (
        'New_swNic_program_regs(false);',
        'New_swNic_program_regs(true);',
        'REG32(MACCTRL1) |= CF_CMAC_CLK_SEL;',
        'iimr &= ~(PKTHDR_DESC_RUNOUT_IE_ALL | MBUF_DESC_RUNOUT_IE_ALL);',
        'bool is_vg = ((REG32(0xB8000000) & 0xFFFFF000u) == 0x81970000u);',
        'REG32(0xB8000850) = 0x579fff7fu;',
        'u32 rx_delay = (p0_rx_delay >= 0) ? ((u32)p0_rx_delay & 7u) : (is_vg ? 7u : 5u);',
        '(v & ~(0x7Fu << 4)) | (0x48u << 4);',
        '(v & ~(0x3Fu << 12)) | (1u << 12);',
        'REG32(RTL819X_SWCORE_BASE + 0x457C) = 0x00fc00ffu;',
        'REG32(RTL819X_SWCORE_BASE + 0x45C4) = 0x00fc00ffu;',
        'if (used > 400 && rx == stall_prev_rx)',
        'if (hang_cnt >= 25)',
        'bool pressure = runout || used > 400;',
        'if (skb_is_nonlinear(skb) && skb_linearize(skb))',
        'if (of_machine_is_compatible("rockspace,rsd0614"))',
        'fabric_gw_rearm = 0;',
        'static int dp_heartbeat;',
        'module_param(dp_heartbeat, int, 0644);',
        'else if (beat && (dp_heartbeat || pc == 1024))',
    ):
        if token not in ethtext:raise ValueError('RTL8197FH-VG RGMII/newdesc/heartbeat/threshold patch missing from compiled rtl819x-eth.c: '+token)
    if 'used > 256' in ethtext:raise ValueError('Stale used > 256 threshold survived in compiled rtl819x-eth.c')
    swnicsrc=linux/'drivers/net/ethernet/rtl819x/rtl819x_swnic.c'
    if not swnicsrc.is_file():raise ValueError('Missing compiled rtl819x_swnic.c: '+str(swnicsrc))
    swnictext=swnicsrc.read_text()
    for token in (
        'struct rtl_new_rx_desc',
        'struct rtl_new_tx_desc',
        'BUILD_BUG_ON(sizeof(struct rtl_new_rx_desc) != 24);',
        'BUILD_BUG_ON(sizeof(struct rtl_new_tx_desc) != 24);',
        'bool rtl819x_use_new_desc(void)',
        'void New_swNic_program_regs(bool post_start)',
        'TX_PKTHDR_SHORTCUT_LSO',
        'REG32(DMA_CR1) = (txCnt - 1) * sizeof(struct rtl_new_tx_desc);',
        'REG32(DMA_CR4) = TX_RING0_TAIL_AWARE;',
        'New_swNic_receive_newdesc',
        'if (!new_desc_active)',
        'REG32(CPUICR) |= TXFD;',
    ):
        if token not in swnictext:raise ValueError('RTL8197FH-VG 6-dword new-descriptor engine missing from compiled rtl819x_swnic.c: '+token)
    if '& ~(1u << 29)' in swnictext:raise ValueError('CPUICR bit 29 (BUSBURST_128WORDS) clobber survived in compiled rtl819x_swnic.c')
    sw8367src=linux/'drivers/net/phy/rtl8367b.c'
    if not sw8367src.is_file():raise ValueError('Missing compiled rtl8367b.c: '+str(sw8367src))
    sw8367text=sw8367src.read_text()
    for token in (
        'static int rtl8367s_set_max_len_1552(struct rtl8366_smi *smi)',
        'rtl8366_smi_rmwr(smi, 0x1200, 0x6000, 0x6000);',
        'rtl8366_smi_rmwr(smi, 0x0884, 0x0003, 0x0003);',
        'rtl8366_smi_write_reg(smi, 0x088c, 0x0610);',
        'rtl8366_smi_write_reg(smi, 0x088d, 0x0610);',
        '(void)rtl8367s_set_max_len_1552(smi);',
        'err = rtl8367s_set_max_len_1552(smi);',
    ):
        if token not in sw8367text:raise ValueError('RTL8367S 1552B max-frame fix missing from compiled rtl8367b.c: '+token)
    regssrc=linux/'drivers/net/ethernet/rtl819x/rtl819x_regs.h'
    if not regssrc.is_file():raise ValueError('Missing compiled rtl819x_regs.h: '+str(regssrc))
    regstext=regssrc.read_text()
    for token in (
        '#define CPUQDM0',
        '#define TX_PKTHDR_SHORTCUT_LSO',
        '#define CF_RXDESC_OFFSET',
        '#define CF_TXDESC_OFFSET',
        '#define MACCTRL1',
        '#define CF_CMAC_CLK_SEL',
    ):
        if token not in regstext:raise ValueError('RTL8197FH-VG new-descriptor register defs missing from compiled rtl819x_regs.h: '+token)
    pcisrc=linux/'arch/mips/pci/pci-realtek.c'
    if not pcisrc.is_file():raise ValueError('Missing compiled pci-realtek.c: '+str(pcisrc))
    pcitext=pcisrc.read_text()
    for token in (
        'if ((sr_r32(REALTEK_SR_REG_ID) & 0xFFFFF000u) == 0x81970000u)',
        'realtek_pcie_mdio_write(rpc, 0x08, 0x3101);',
        'mdelay(290);',
        'for (attempt = 1; attempt <= 3; attempt++)',
        'sr_w32(val & ~BIT(14), REALTEK_SR_CLKMANAGE);',
    ):
        if token not in pcitext:raise ValueError('RTL8197FH-VG 40MHz PCIe MDIO/reset/retry hardening missing from compiled pci-realtek.c: '+token)
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
    if IRQ_SAFE_BLOCK not in irqtext:raise ValueError('RSD0614 M3 direct-IRQ mask hardening missing from compiled source')
    surveysrc=linux/'arch/mips/realtek/rsd0614_survey.c'
    if not surveysrc.is_file():raise ValueError('Missing compiled omnibus survey source: '+str(surveysrc))
    surveytext=surveysrc.read_text()
    for token in (
        'of_machine_is_compatible("rockspace,rsd0614")',
        'proc_create("rsd0614_hw_survey", 0444, NULL, &rsd0614_hw_survey_fops)',
        '.write = NULL,',
        'proc_create("rsd0614_probe", 0600, NULL, &rsd0614_probe_fops)',
        "if (*cmd == '\\0')",
        'RSD0614_MDCIOCR_REG',
        'RSD0614_PINMUX_SMI_GPIO',
        '0x13C2U, 0x0249U',
        'orig_64 = sr_r32(REALTEK_SR_WLAN_EN);',
        'sr_w32(orig_64, REALTEK_SR_WLAN_EN);',
        'if ((ltssm & 0x1fU) == 0x11U)',
        'RSD0614_PCIE0_EP_CFG',
        'late_initcall(rsd0614_survey_init);',
    ):
        if token not in surveytext:raise ValueError('RSD0614 omnibus survey/probe guard missing from compiled source: '+token)
    if 'while (1)' in surveytext:raise ValueError('Unbounded while (1) loop found in rsd0614_survey.c')
    if 'smi_write_reg(bus, 0x1322' in surveytext or 'mdio_8367_write_reg(phy_id, 0x1322' in surveytext:raise ValueError('Forbidden RTL8367 chip reset write found in rsd0614_survey.c')
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
    wifidir=linux.parent/'rtl8192cd-rsd0614'
    wifiko=wifidir/'rtl8192cd.ko'
    if not wifiko.is_file():raise ValueError('Missing compiled M3 rtl8192cd.ko: '+str(wifiko))
    sysmap=linux/'System.map'
    if not sysmap.is_file():raise ValueError('Missing System.map for ksymtab verification: '+str(sysmap))
    ksymtab=parse_system_map_ksymtab(sysmap.read_text())
    if len(ksymtab)<500:raise ValueError(f'Unexpectedly small vmlinux __ksymtab ({len(ksymtab)} symbols)')
    ko_info=parse_elf32_le_kmod_info(wifiko.read_bytes())
    missing_syms=sorted(set(ko_info['undef_symbols'])-ksymtab)
    if missing_syms:raise ValueError('Unresolved rtl8192cd.ko symbols missing from vmlinux __ksymtab: '+', '.join(missing_syms))
    for req_def in ('rtl8192cd_proc_init','rtl_giwname'):
        if req_def not in ko_info['defined_symbols']:
            raise ValueError('Required v5.6.3 global symbol missing from compiled rtl8192cd.ko: '+req_def)
    if ko_info['bss_bytes']>1536*1024:raise ValueError(f'rtl8192cd.ko .bss too large for 64 MiB RAM: {ko_info["bss_bytes"]} bytes')
    boardsrc=wifidir/'linux6/rtl8192cd_board.c';socsrc=wifidir/'linux6/rtl8197f_soc.c';compatsrc=wifidir/'rtl8197f_linux_compat.h'
    coretxsrc=wifidir/'core/8192cd_core_tx.c';cfghsrc=wifidir/'8192cd_cfg.h';osdepsrc=wifidir/'8192cd_osdep.c'
    comapisrc=wifidir/'8192cd_comapi.c';ioctlsrc=wifidir/'8192cd_ioctl.c'
    txdescsrc=wifidir/'WlanHAL/RTL88XX/Hal88XXTxDesc.c';halgensrc=wifidir/'WlanHAL/RTL88XX/Hal88XXGen.c'
    h8814bcfg=wifidir/'WlanHAL/RTL88XX/RTL8814B/Hal8814BCfg.h';h8197ggen=wifidir/'WlanHAL/RTL88XX/RTL8197G/Hal8197GGen.c'
    halfwsrc=wifidir/'WlanHAL/RTL88XX/Hal88XXFirmware.c'
    for p in (boardsrc,socsrc,compatsrc,coretxsrc,cfghsrc,osdepsrc,comapisrc,ioctlsrc,txdescsrc,halgensrc,h8814bcfg,h8197ggen,halfwsrc):
        if not p.is_file():raise ValueError('Missing compiled M3 Wi-Fi source evidence: '+str(p))
    boardtext=boardsrc.read_text()
    for token in ('get_mtd_device_nm("cfg")','mtd_read(','put_mtd_device(','rockspace,rsd0614','mac_pton(ascii_mac, addr)','keeping fallback'):
        if token not in boardtext:raise ValueError('M3 read-only MTD cfg / MAC fallback missing from compiled rtl8192cd_board.c: '+token)
    for forbidden in ('mtd_write','mtd_erase','mtd_unlock'):
        if forbidden in boardtext:raise ValueError('Forbidden flash write API in compiled rtl8192cd_board.c: '+forbidden)
    soctext=socsrc.read_text()
    for token in ('BIT(29)','0xB8003000','0xB8003004','& ~BIT(29)'):
        if token not in soctext:raise ValueError('M3 WMAC GIMR BIT(29) probe-mask guard missing from compiled rtl8197f_soc.c: '+token)
    if '| BIT(29)' in soctext:raise ValueError('rtl8197f_soc.c must not unmask GIMR BIT(29) before request_irq()')
    coretxtext=coretxsrc.read_text(errors='replace')
    if 'LINUX_VERSION_CODE < KERNEL_VERSION(4,5,0)' not in coretxtext:raise ValueError('sk_pacing_shift_update 4.14 guard missing from compiled 8192cd_core_tx.c')
    cfgtext=cfghsrc.read_text(errors='replace')
    for token in ('CONFIG_RTL_SHRINK_MEMORY_SIZE','#define NUM_TX_DESC         256','#define MAX_RX_BUF_LEN      2600','(!defined(CONFIG_RTL8192CD_LINUX6_BUS) || (LINUX_VERSION_CODE < KERNEL_VERSION(5, 0, 0)))'):
        if token not in cfgtext:raise ValueError('64 MiB memory shrink / _INCLUDE_PROC_FS_ override missing from compiled 8192cd_cfg.h: '+token)
    osdeptext=osdepsrc.read_text(errors='replace')
    for token in ('GET_CHIP_VER(priv) == VERSION_8814B','!defined(CONFIG_RTL8192CD_LINUX6_BUS)','__raw_readl((void __iomem *)0xB8003000UL) | BIT(29)','(void)REG32(0xB8000064);','SET_NETDEV_DEV(dev, priv->pshare->linux_dev);','u2Byte HIQ_En = 0;','PrepareTXBDHandler(priv) == RT_STATUS_FAILURE','desc_dma_buf_virt_amsdu','dot11RsnIE.rsnielen = 0;'):
        if token not in osdeptext:raise ValueError('v5.6.3 RTL8814B/WMAC/SET_NETDEV_DEV/HIQ_En hardening missing from compiled 8192cd_osdep.c: '+token)
    if 'int rtl_giwname(' not in comapisrc.read_text(errors='replace'):raise ValueError('rtl_giwname WEXT SIOCGIWNAME handler missing from compiled 8192cd_comapi.c')
    if '(iw_handler) rtl_giwname,' not in ioctlsrc.read_text(errors='replace'):raise ValueError('rtl_giwname SIOCGIWNAME wiring missing from compiled 8192cd_ioctl.c')
    if '#define TX_HIQ_NUM_8814B                20' not in h8814bcfg.read_text(errors='replace'):
        raise ValueError('RTL8814B 20-HIQ alignment missing from compiled Hal8814BCfg.h')
    txdesctext=txdescsrc.read_text(errors='replace')
    for token in ('coherent_tx ? coherent_bd','HCI_TX_DMA_QUEUE_HI0_V2','REG_HI16Q_TXBD_DESA_L','rsd0614_amsdu_txbd_dma','IE0_SET_TX_DESC_DATARATE(IE0_head, 4)','alloc_desc_bcn_addr'):
        if token not in txdesctext:raise ValueError('v5.6.3 RTL8814B/8197G TXBD/AMSDU/BCN fix missing from compiled Hal88XXTxDesc.c: '+token)
    halgentext=halgensrc.read_text(errors='replace')
    for token in ('Adapter->pshare->InterruptMaskExt = _GET_HAL_DATA(Adapter)->IntMask[1];','REG_P0HI16Q_HI17Q_TXBD_NUM','HCI_TX_DMA_QUEUE_CMD_V2','tmp1byte = HAL_RTL_R8(REG_AUTO_LLT_V1) | BIT0;'):
        if token not in halgentext:raise ValueError('v5.6.3 Hal88XXGen TXBD/LLT/IMR fix missing from compiled Hal88XXGen.c: '+token)
    h8197gtext=h8197ggen.read_text(errors='replace')
    for token in ('MappingTxQueue88XX;','CAMProgramEntry88XX_V1;'):
        if token not in h8197gtext:raise ValueError('v5.6.3 RTL8197G 15-queue / WPA2 CAM v1 fix missing from compiled Hal8197GGen.c: '+token)
    if 'wait_cnt = 0;' not in halfwsrc.read_text(errors='replace'):
        raise ValueError('v5.6.3 DownloadRsvdPage88XX wait_cnt reset missing from compiled Hal88XXFirmware.c')
    text=Path(log).read_text(errors='replace')
    boards=re.findall(r'BOARD="([^"]+)"[^\n]*SUBTARGET="rtl8197f"',text)
    if not boards or any(b!='RSD0614' for b in boards):raise ValueError('Loader BOARD not exclusively RSD0614: '+repr(boards))
    manifest=[]
    for name,rel in [('kernel.config','.config'),('System.map','System.map'),('vmlinux','vmlinux'),('vmlinux-initramfs.elf','../vmlinux-initramfs.elf'),('vmlinux-initramfs.debug','../vmlinux-initramfs.debug'),('spi-nor.c','drivers/mtd/spi-nor/spi-nor.c'),('spi-sheipa.c','drivers/spi/spi-sheipa.c'),('irq.c','arch/mips/realtek/irq.c'),('rsd0614_survey.c','arch/mips/realtek/rsd0614_survey.c'),('rtl819x-eth.c','drivers/net/ethernet/rtl819x/rtl819x-eth.c'),('rtl819x_swnic.c','drivers/net/ethernet/rtl819x/rtl819x_swnic.c'),('rtl819x_regs.h','drivers/net/ethernet/rtl819x/rtl819x_regs.h'),('rtl8367b.c','drivers/net/phy/rtl8367b.c'),('pci-realtek.c','arch/mips/pci/pci-realtek.c'),('serial_reg.h','include/uapi/linux/serial_reg.h'),('8250_dw.c','drivers/tty/serial/8250/8250_dw.c'),('rtl8192cd_board.c','../rtl8192cd-rsd0614/linux6/rtl8192cd_board.c'),('rtl8197f_soc.c','../rtl8192cd-rsd0614/linux6/rtl8197f_soc.c'),('rtl8197f_linux_compat.h','../rtl8192cd-rsd0614/rtl8197f_linux_compat.h'),('8192cd_core_tx.c','../rtl8192cd-rsd0614/core/8192cd_core_tx.c'),('8192cd_cfg.h','../rtl8192cd-rsd0614/8192cd_cfg.h')]:
        path=linux/rel
        if not path.is_file():raise ValueError('Missing build evidence: '+str(path))
        shutil.copyfile(path,dest/name)
        manifest.append({'name':name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    provenance={'port_input_fingerprint':port_fingerprint,'project_commit':project_commit,'builder_image_id':builder_image_id}
    kmod_audit={'vmlinux_ksymtab_count':len(ksymtab),'rtl8192cd_undef_symbol_count':len(ko_info['undef_symbols']),'rtl8192cd_missing_symbols':missing_syms,'rtl8192cd_bss_bytes':ko_info['bss_bytes'],'rtl8192cd_has_proc_init':'rtl8192cd_proc_init' in ko_info['defined_symbols'],'rtl8192cd_has_giwname':'rtl_giwname' in ko_info['defined_symbols']}
    (dest/'manifest.json').write_text(json.dumps({'files':manifest,'loader_board_values':boards,'provenance':provenance,'kmod_symbol_audit':kmod_audit},indent=2)+'\n')
    print(f"GENERATED_KERNEL_CONFIG_AND_SOURCE: PASS; rtl8192cd_undef={len(ko_info['undef_symbols'])} missing=0 bss={ko_info['bss_bytes']}B proc_init=1 giwname=1; hardware execution remains unverified")

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tree');p.add_argument('out');p.add_argument('--log',required=True);p.add_argument('--port-fingerprint',default='NOT_RECORDED');p.add_argument('--project-commit',default='NOT_AVAILABLE');p.add_argument('--builder-image-id',default='NOT_RECORDED');a=p.parse_args()
    try:export(a.tree,a.out,a.log,port_fingerprint=a.port_fingerprint,project_commit=a.project_commit,builder_image_id=a.builder_image_id)
    except (OSError,ValueError) as e:raise SystemExit('BUILD_EVIDENCE: FAIL: '+str(e))
