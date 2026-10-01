#!/usr/bin/env python3
"""Offline structural audit for this pinned RTL8197F initramfs pipeline.

Parses bytes only: never executes the image, extracts device nodes/symlinks,
contacts a router, or declares a hardware boot successful. Bounds are deliberate.
This is not a general ELF verifier or proof of no MMIO/flash side effects.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import lzma
import re
import stat
import struct

MAX_IMAGE=16*1024*1024
MAX_OUTPUT=16*1024*1024-1
PARTS={'bootloader':(0,0x20000),'cfg':(0x20000,0x10000),'firmware':(0x30000,0x7a0000),'cpe':(0x7d0000,0x10000),'cfm':(0x7e0000,0x10000),'cfm_backup':(0x7f0000,0x10000)}

def align4(n):return (n+3)&~3

def unpack_lzma(image):
    if not 65536<=len(image)<=MAX_IMAGE: raise ValueError('Image outside the bounded first-candidate size range')
    hits=[]
    for off in range(min(65536,len(image)-13)):
        prop=image[off]
        if prop>=225:continue
        lc=prop%9; rem=prop//9;lp=rem%5
        if lc+lp>4:continue
        dictionary=struct.unpack_from('<I',image,off+1)[0]
        if dictionary not in {1<<n for n in range(12,25)}:continue
        expected=struct.unpack_from('<Q',image,off+5)[0]
        if not 0x10000<=expected<=MAX_OUTPUT:continue
        try:
            dec=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE,memlimit=128*1024*1024)
            payload=dec.decompress(image[off:],max_length=expected+1)
            if not dec.eof or len(payload)!=expected:continue
            if b'Linux version ' not in payload:continue
        except lzma.LZMAError:continue
        hits.append((off,payload,{'stream_offset':off,'properties':prop,'dictionary_size':dictionary,'decoded_size':len(payload),'stream_consumed':len(image)-off-len(dec.unused_data),'trailing_bytes':len(dec.unused_data)}))
    if len(hits)!=1:raise ValueError(f'Expected one bounded Linux LZMA stream, found {len(hits)}')
    return hits[0][1],hits[0][2]

def parse_fdt(blob):
    if len(blob)<40:raise ValueError('Truncated FDT header')
    magic,total,so,st,ro,version,last,cpu,ns,nstruct=struct.unpack_from('>10I',blob)
    if magic!=0xd00dfeed or total>len(blob) or total<40 or version!=17:raise ValueError('Unsupported FDT header')
    if so+nstruct>total or st+ns>total or ro>=total:raise ValueError('FDT offsets out of bounds')
    strings=blob[st:st+ns];pos=so;end=so+nstruct;stack=[];tree={};finished=False
    def word():
        nonlocal pos
        if pos+4>end:raise ValueError('Truncated FDT token')
        val=struct.unpack_from('>I',blob,pos)[0];pos+=4;return val
    while pos<end:
        token=word()
        if token==1:
            z=blob.find(b'\0',pos,end)
            if z<0:raise ValueError('FDT node name is unterminated')
            name=blob[pos:z].decode('ascii');stack.append(name);pos=align4(z+1);path='/'.join(stack) or '/'
            if path in tree:raise ValueError('Duplicate FDT node')
            tree[path]={}
        elif token==2:
            if not stack:raise ValueError('Unbalanced FDT node')
            stack.pop()
        elif token==3:
            size=word();s=word()
            if not stack or pos+size>end or s>=len(strings):raise ValueError('FDT property bounds')
            z=strings.find(b'\0',s)
            if z<0:raise ValueError('FDT property name is unterminated')
            key=strings[s:z].decode('ascii');path='/'.join(stack) or '/'
            if key in tree[path]:raise ValueError('Duplicate FDT property')
            tree[path][key]=blob[pos:pos+size];pos=align4(pos+size)
        elif token==4:pass
        elif token==9:
            if stack:raise ValueError('FDT ended inside node')
            finished=True;break
        else:raise ValueError('Unknown FDT token')
    if not finished:raise ValueError('Missing FDT end token')
    return tree,total

def find_fdt(payload):
    found=[]
    for match in re.finditer(b'\xd0\x0d\xfe\xed',payload):
        off=match.start()
        try:
            tree,size=parse_fdt(payload[off:])
            if off+size==len(payload):found.append((tree,off,size))
        except (ValueError,UnicodeError,struct.error):pass
    if len(found)!=1:raise ValueError('Expected a single terminal appended DTB')
    return found[0]

def parse_cpio(data,base=0):
    pos=base;entries=[];seen={}
    for _ in range(10000):
        if pos+110>len(data) or data[pos:pos+6] not in (b'070701',b'070702'):raise ValueError('Invalid/truncated newc header')
        crc=data[pos:pos+6]==b'070702';raw=data[pos+6:pos+110]
        if not re.fullmatch(rb'[0-9a-fA-F]{104}',raw):raise ValueError('Invalid newc numeric field')
        f=[int(raw[i:i+8],16) for i in range(0,104,8)]
        ino,mode,uid,gid,nlink,mtime,size,major,minor,rmajor,rminor,namesize,check=f
        if not 1<=namesize<=4096 or size>MAX_OUTPUT:raise ValueError('Unbounded CPIO member')
        s=pos+110;e=s+namesize
        if e>len(data) or data[e-1]!=0:raise ValueError('CPIO name bounds')
        name=data[s:e].rstrip(b'\0').decode('utf-8')
        if '\0' in name:raise ValueError('Embedded NUL in CPIO name')
        if name.startswith('./'):name=name[2:]
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:raise ValueError('Unsafe CPIO path')
        dp=align4(e);nxt=align4(dp+size)
        if nxt>len(data):raise ValueError('Truncated CPIO data')
        body=data[dp:dp+size]
        if crc and sum(body)&0xffffffff!=check:raise ValueError('CPIO crc checksum mismatch')
        entry={'path':name,'mode':mode,'inode':ino,'uid':uid,'gid':gid,'nlink':nlink,'mtime':mtime,'major':major,'minor':minor,'rmajor':rmajor,'rminor':rminor,'data':body,'hardlink_key':(major,minor,ino),'archive_offset':pos-base}
        previous=seen.get(name)
        if previous is not None:
            semantic=('mode','uid','gid','nlink','mtime','major','minor','rmajor','rminor','data')
            if any(previous[k]!=entry[k] for k in semantic):raise ValueError('Conflicting duplicate CPIO pathname: '+name)
            entry['duplicate_of_archive_offset']=previous['archive_offset']
        else:seen[name]=entry
        entries.append(entry);pos=nxt
        if name=='TRAILER!!!':
            if size:raise ValueError('Nonempty CPIO trailer')
            return entries,pos
    raise ValueError('CPIO entry budget exceeded')

def find_cpio(payload):
    found=[];last_end=-1;attempts=0
    for match in re.finditer(b'07070[12]',payload):
        off=match.start()
        if off<last_end:continue
        attempts+=1
        if attempts>512:raise ValueError('Too many CPIO candidates')
        try:
            entries,end=parse_cpio(payload,off);names={e['path'] for e in entries}
            if len(entries)>=100 and {'init','etc/inittab'}<=names:found.append((entries,off,end));last_end=end
        except (ValueError,UnicodeError):pass
    if len(found)!=1:raise ValueError('Expected one complete embedded root CPIO')
    return found[0]

def flash_table(payload):
    def entry(off):
        if off<0 or off+24>len(payload):return None
        ptr,ident,idlen,sector,nsectors,page,addr,flags=struct.unpack_from('<I6sBxI4H',payload,off);no=ptr-0x80000000
        if not 0<=no<len(payload):return None
        z=payload.find(b'\0',no,min(no+64,len(payload)))
        if z<0:return None
        name=payload[no:z]
        if not re.fullmatch(rb'[a-zA-Z0-9_.-]+',name):return None
        if idlen>6 or sector>1<<25 or nsectors>32768 or page>8192 or addr>4:return None
        return {'name':name.decode(),'id':ident[:idlen].hex(),'id_len':idlen,'sector_size':sector,'n_sectors':nsectors,'page_size':page,'flags':flags,'offset':off}
    names=[m.start() for m in re.finditer(b'w25q64\0',payload)];tables={}
    for n in names:
        ptr=struct.pack('<I',0x80000000+n)
        for m in re.finditer(re.escape(ptr),payload):
            start=m.start()
            if entry(start) is None:continue
            budget=0
            while entry(start-24) is not None and budget<1000:start-=24;budget+=1
            rows=[];p=start
            for _ in range(1500):
                e=entry(p)
                if e is None:break
                rows.append(e);p+=24
            if len(rows)>=80 and payload[p:p+24]==bytes(24):tables[start]=rows
    if len(tables)!=1:raise ValueError('Could not uniquely decode the pinned SPI-NOR ID table')
    start,rows=next(iter(tables.items()));return rows,start

def audit(image):
    payload,lz=unpack_lzma(image);tree,dtboff,dtbsize=find_fdt(payload);entries,cpiooff,cpioend=find_cpio(payload);duplicate_paths=sorted({e['path'] for e in entries if 'duplicate_of_archive_offset' in e});table,tableoff=flash_table(payload);checks=[]
    def check(name,ok,detail=''):checks.append({'check':name,'pass':bool(ok),'detail':detail})
    check('target-compatible',b'rockspace,rsd0614\0' in tree['/'].get('compatible',b''));check('target-model',tree['/'].get('model')==b'Rock Space RSD0614 V1.0\0')
    memories=[p for p in tree.values() if p.get('device_type')==b'memory\0'];check('64MiB-memory',len(memories)==1 and memories[0].get('reg')==struct.pack('>II',0,0x4000000))
    check('UART-115200-initcall-debug-keep-bootcon',tree.get('/chosen',{}).get('bootargs')==b'console=ttyS0,115200 initcall_debug ignore_loglevel keep_bootcon\0')
    uart=tree.get('/serial@18147000',{})
    uart_compat=uart.get('compatible',b'')
    check('RTL8197F-UART-exact-geometry',
          b'realtek,rtl8197f-uart\0' in uart_compat and b'snps,dw-apb-uart\0' in uart_compat and
          uart.get('reg')==struct.pack('>II',0x18147000,0x100) and
          uart.get('interrupts')==struct.pack('>I',9) and
          uart.get('reg-io-width')==struct.pack('>I',4) and
          uart.get('reg-shift')==struct.pack('>I',2) and
          uart.get('clock-frequency')==struct.pack('>I',100000000) and
          uart.get('status')==b'okay\0')
    for path in ('/spi@18143000','/pcie-controller@18b00000','/pcie-controller@18b20000','/wmac@18640000','/ethernet@18010000'):check('disabled:'+path,tree.get(path,{}).get('status')==b'disabled\0')
    parts={}
    for path,props in tree.items():
        if '/partition@' in path:
            label=props.get('label',b'').rstrip(b'\0').decode('ascii')
            if label in parts:raise ValueError('Duplicate partition label')
            parts[label]={'reg':props.get('reg',b''),'read_only':'read-only' in props}
    check('six-exact-readonly-partitions',set(parts)==set(PARTS) and all(parts[n]['reg']==struct.pack('>II',*geom) and parts[n]['read_only'] for n,geom in PARTS.items()))
    check('decompression-output-below-loader',0x80000000+len(payload)<=0x81000000);check('compressed-input-inside-64MiB',0x81000000+len(image)<=0x84000000)
    byname={e['path']:e for e in entries};init=byname['init']['data'];check('initramfs-mode',b'INITRAMFS=1' in init)
    forbidden=[]
    for name in byname:
        low=name.lower()
        if any(x in low for x in ('dir842','asic-wifi-settle','09_fix-header','30-hwnat','rtl8192cd')):forbidden.append(name)
    check('no-donor-userspace',not forbidden,', '.join(forbidden));marker=byname.get('etc/rsd0614-diagnostic-mode',{}).get('data');check('diagnostic-mode-marker',marker==b'v5.3.8-uart-register-semantics\n');done=byname.get('etc/init.d/done',{}).get('data',b'');check('diagnostic-done-no-mount-root',bool(done) and b'mount_root' not in done and b'set_state done' in done);boot=byname.get('etc/init.d/boot',{}).get('data',b'');check('diagnostic-boot-no-mount-root',bool(boot) and b'mount_root' not in boot and b'config_generate' in boot and b'kmodloader' in boot);defaultnet=byname.get('etc/board.d/99-default_network',{}).get('data',b'');check('no-default-physical-interface-synthesis',bool(defaultnet) and b"ucidef_set_interface_lan 'eth0'" not in defaultnet and b'eth1' not in defaultnet and b'board_config_flush' in defaultnet);preinit_mount=byname.get('lib/preinit/80_mount_root',{}).get('data',b'');check('preinit-mount-root-initramfs-guard',b'[ "$INITRAMFS" = "1" ] || boot_hook_add preinit_main do_mount_root' in preinit_mount)
    network=byname.get('etc/config/network',{}).get('data',b'');check('loopback-only-defaults',b"'loopback'" in network and not re.search(rb'\b(?:eth\d|wlan\d|wan|lan)\b',network));check('cpio-duplicate-paths-consistent',True,', '.join(duplicate_paths) if duplicate_paths else 'none')
    matches=[row for row in table if row['id']=='684017' and row['id_len']==3];check('BH25Q64-exact-id-and-geometry',len(matches)==1 and matches[0]['sector_size']==65536 and matches[0]['n_sectors']==128)
    if matches:check('BH25Q64-conservative-flags',matches[0]['flags']==0x2008)
    banner=re.search(rb'Linux version [^\x00\n]+',payload)
    return {'image_size':len(image),'image_sha256':hashlib.sha256(image).hexdigest(),'lzma':lz,'kernel_banner':banner.group().decode(errors='replace') if banner else None,'dtb_offset_in_payload':dtboff,'dtb_size':dtbsize,'cpio_offset_in_payload':cpiooff,'cpio_end':cpioend,'cpio_entries_including_trailer':len(entries),'cpio_duplicate_paths':duplicate_paths,'flash_table_offset':tableoff,'flash_table_entry_count':len(table),'bh25q64_entries':matches,'checks':checks,'offline_policy_result':'PASS' if all(c['pass'] for c in checks) else 'FAIL','boot_qualification':'NOT YET VERIFIED','ram_boot_authorized':False,'limitations':['No MIPS execution or hardware run.','No proof of kernel BSS/workspace bounds without ELF and runtime review.','Read-only partition flags are not a proof of zero hardware-register writes.','The parser targets this pinned little-endian MIPS32/uncompressed-CPIO pipeline.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('--json',type=Path);a=p.parse_args()
    try:
        path=Path(a.image)
        if path.stat().st_size>MAX_IMAGE:raise ValueError('Image too large')
        report=audit(path.read_bytes())
    except (OSError,ValueError,struct.error,lzma.LZMAError) as e:report={'offline_policy_result':'FAIL','error':str(e),'ram_boot_authorized':False,'boot_qualification':'NOT YET VERIFIED'}
    if a.json:a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(report,indent=2)+'\n')
    print('OFFLINE_POLICY_AUDIT:',report['offline_policy_result'])
    for c in report.get('checks',[]):print(('PASS' if c['pass'] else 'FAIL')+' '+c['check']+((': '+c['detail']) if c['detail'] else ''))
    if 'error' in report:print(report['error'])
    print('BOOT_QUALIFICATION: NOT YET VERIFIED\nRAM_BOOT_AUTHORIZED: NO');return 0 if report['offline_policy_result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
