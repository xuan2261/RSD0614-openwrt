"""Parser/source regressions only. Synthetic fixtures never count as a hardware test."""
from pathlib import Path
import hashlib,json,lzma,re,struct,subprocess,tempfile,unittest
import deep_audit as da
import harden_source as hs
ROOT=Path(__file__).resolve().parent

def newc(name,body=b'',mode=0o100644,ino=1):
    name=name.encode()+b'\0';f=(ino,mode,0,0,1,0,len(body),0,0,0,0,len(name),0);header=b'070701'+b''.join(f'{x:08x}'.encode() for x in f)+name;header+=b'\0'*((-len(header))%4);return header+body+b'\0'*((-len(body))%4)
class ParserTests(unittest.TestCase):
 def test_cpio_regular_and_trailer(self):
  data=newc('init',b'hello')+newc('TRAILER!!!',ino=2);e,end=da.parse_cpio(data);self.assertEqual(e[0]['data'],b'hello');self.assertEqual(end,len(data))
 def test_cpio_symlink_only_parsed(self):
  data=newc('link',b'../init',0o120777)+newc('TRAILER!!!',ino=2);e,_=da.parse_cpio(data);self.assertEqual(e[0]['data'],b'../init')
 def test_cpio_path_traversal_rejected(self):
  for n in ('../x','/etc/passwd','x/../../y'):
   with self.subTest(n=n),self.assertRaises(ValueError):da.parse_cpio(newc(n))
 def test_cpio_truncation_rejected(self):
  with self.assertRaises(ValueError):da.parse_cpio(newc('init',b'abc')[:-1])
 def test_cpio_identical_duplicate_allowed_and_marked(self):
  data=newc('init')+newc('init',ino=2)+newc('TRAILER!!!',ino=3);e,_=da.parse_cpio(data);self.assertEqual(len(e),3);self.assertEqual(e[1]['duplicate_of_archive_offset'],0)
 def test_cpio_conflicting_duplicate_rejected(self):
  with self.assertRaises(ValueError):da.parse_cpio(newc('init',b'a')+newc('init',b'b',ino=2))
 def test_find_cpio_keeps_earliest_root_archive_with_safe_duplicates(self):
  parts=[newc('dev',mode=0o040755,ino=1)]+[newc(f'file{i:03d}',ino=i+10) for i in range(100)]+[newc('init',ino=200),newc('etc/inittab',ino=201),newc('dev',mode=0o040755,ino=202),newc('TRAILER!!!',ino=203)];entries,start,end=da.find_cpio(b''.join(parts));self.assertEqual(start,0);self.assertEqual(len(entries),105);self.assertEqual(entries[-2]['path'],'dev');self.assertIn('duplicate_of_archive_offset',entries[-2])
 def test_cpio_count_bounds(self):
  d=bytearray(newc('init'));d[94:102]=b'ffffffff'
  with self.assertRaises(ValueError):da.parse_cpio(bytes(d))
 def test_fdt_truncation_rejected(self):
  with self.assertRaises(ValueError):da.parse_fdt(b'\xd0\x0d\xfe\xed')
 def test_fdt_bounds_rejected(self):
  with self.assertRaises(ValueError):da.parse_fdt(struct.pack('>10I',0xd00dfeed,40,400,800,16,17,16,0,4,8))
 def test_no_lzma_rejected(self):
  with self.assertRaises(ValueError):da.unpack_lzma(bytes(65536))
 def test_lzma_actual_roundtrip(self):
  payload=b'Linux version fixture\0'+bytes(range(256))*300
  from lzma_test_fixture import load_fixture
  encoded=load_fixture();image=bytes(65536)+bytes(encoded)
  with self.assertRaises(ValueError):da.unpack_lzma(image)
  image=bytes(1024)+bytes(encoded)+bytes(65536);decoded,info=da.unpack_lzma(image);self.assertEqual(decoded,payload);self.assertEqual(info['stream_offset'],1024)
 def test_no_spi_table_is_unknown_not_pass(self):
  with self.assertRaises(ValueError):da.flash_table(b'BH25Q64\x68\x40\x17'+bytes(65536))
 def test_flash_struct_size(self):self.assertEqual(struct.calcsize('<I6sBxI4H'),24)
class SourceTests(unittest.TestCase):
 def test_dev_profile_added_once(self):
  src='DEVICE_VARS += IMAGE_SIZE\ndefine Device/RSD0614\nendef\n';once=hs.patch_image_makefile(src);self.assertEqual(hs.patch_image_makefile(once),once);self.assertIn('IMAGE_SIZE DEV_PROFILE',once)
 def test_missing_device_rejected(self):
  with self.assertRaises(ValueError):hs.patch_image_makefile('DEVICE_VARS += IMAGE_SIZE\n')
 def test_missing_export_anchor_rejected(self):
  with self.assertRaises(ValueError):hs.patch_image_makefile('define Device/RSD0614\nendef\n')
 def test_irq_diagnostic_mask_patch_idempotent(self):
  src='prefix\n'+hs.IRQ_UNSAFE_BLOCK+'\nsuffix\n';one=hs.patch_irq_source(src);self.assertEqual(hs.patch_irq_source(one),one);self.assertIn('ic_w32(0, REALTEK_IC_REG_MASK);',one);self.assertIn('REALTEK_IC_REG_STATUS',one);self.assertIn('return 0;',one);self.assertNotIn('// Return only MARK1',one)
 def test_done_script_never_mounts_persistent_root(self):
  done=hs.BASE_FILES['etc/init.d/done'];self.assertNotIn('mount_root',done);self.assertNotIn('/dev/mtd',done);self.assertNotIn('sysupgrade',done);self.assertIn('set_state done',done)
 def test_boot_script_removes_persistent_root_fallback(self):
  src='#!/bin/sh /etc/rc.common\nboot() {\n'+hs.BOOT_MOUNT_ROOT_LINE+'\t/sbin/kmodloader\n}\n';one=hs.patch_boot_script(src);self.assertEqual(hs.patch_boot_script(one),one);self.assertNotIn('mount_root',one);self.assertIn('kmodloader',one)
 def test_default_network_does_not_synthesize_eth_interfaces(self):
  src=". /lib/functions/uci-defaults.sh\nboard_config_update\n"+hs.DEFAULT_NETWORK_UNSAFE+"board_config_flush\n";one=hs.patch_default_network_script(src);self.assertEqual(hs.patch_default_network_script(one),one);self.assertNotIn("ucidef_set_interface_lan 'eth0'",one);self.assertNotIn('eth1',one);self.assertIn('board_config_flush',one)
 def test_kernel_config_idempotent(self):
  src='CONFIG_NET_RTL819X=y\nCONFIG_RTL8192CD=m\nCONFIG_SPI_SHEIPA=y\n';one=hs.patch_kernel_config(src);self.assertEqual(hs.patch_kernel_config(one),one);self.assertIn('CONFIG_SPI_SHEIPA=y',one)
  for key in hs.DISABLE_KERNEL:self.assertIn('# '+key+' is not set',one)
 def test_loopback_files_no_physical_operations(self):
  for body in hs.BASE_FILES.values():
   for forbidden in ('/dev/mtd','swconfig ','/sys/module/rtl819x','/proc/rtl865','192.168.'):self.assertNotIn(forbidden,body)
 def test_all_local_shell_fragments_parse(self):
  for name,body in hs.BASE_FILES.items():
   if body.startswith('#!'):
    p=subprocess.run(['sh','-n'],input=body,text=True,capture_output=True);self.assertEqual(p.returncode,0,(name,p.stderr))
 def test_make_late_global_reproduction_and_fix(self):
  prefix='DEV_PROFILE := RSD0614\n';suffix='DEV_PROFILE := ACTIONRF1200\nall:\n\t@printf "%s\\n" "$(DEV_PROFILE)"\n'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'Makefile';p.write_text(prefix+suffix);old=subprocess.check_output(['make','-s','-C',td],text=True).strip();p.write_text(prefix+'all: DEV_PROFILE := $(DEV_PROFILE)\n'+suffix);new=subprocess.check_output(['make','-s','-C',td],text=True).strip();self.assertEqual(old,'ACTIONRF1200');self.assertEqual(new,'RSD0614')
 def test_nor_patch_applies_and_is_conservative(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'drivers/mtd/spi-nor/spi-nor.c';p.parent.mkdir(parents=True);p.write_text('/* bounded fixture using pinned upstream table context */\nstatic const struct flash_info spi_nor_ids[] = {\n\t/* Atmel -- some are (confusingly) marketed as "DataFlash" */\n\t{ "at25fs010",  INFO(0x1f6601, 0, 32 * 1024,   4, SECT_4K) },\n\t{ },\n};\n');run=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(ROOT/'patches'/hs.PATCH_NAME)],cwd=td,text=True,capture_output=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr);t=p.read_text();self.assertIn('INFO(0x684017, 0, 64 * 1024, 128',t);self.assertIn('SPI_NOR_NO_FR | SPI_NOR_SKIP_SFDP',t);self.assertNotIn('SPI_NOR_QUAD_READ',t)
 def test_uart_rxtx_patch_applies_and_is_scoped(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'include/uapi/linux/serial_reg.h';p.parent.mkdir(parents=True);p.write_text('/*\n * DLAB=0\n */\n#define UART_RX\t\t0\t/* In:  Receive buffer */\n#define UART_TX\t\t0\t/* Out: Transmit buffer */\n\n#define UART_IER\t1\t/* Out: Interrupt Enable Register */\n');run=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(ROOT/'patches'/hs.UART_PATCH_NAME)],cwd=td,text=True,capture_output=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr);u=p.read_text();self.assertIn('#ifdef CONFIG_SOC_RTL8197F',u);self.assertRegex(u,r'#define UART_RX\s+9\b');self.assertRegex(u,r'#define UART_TX\s+9\b');self.assertRegex(u,r'#else\n#define UART_RX\s+0\b')
 def test_builder_v534_volume_separate(self):
  t=(ROOT/'Build-RSD0614.ps1').read_text(encoding='utf-8-sig');self.assertIn('rsd0614-openwrt-builder:v5.1',t);self.assertIn('rsd0614-openwrt-v534-work',t);self.assertIn("-ne 'v5.3.4'",t);self.assertIn('rsd0614.work=v5.3.4',t);self.assertNotIn('rsd0614-openwrt-v532-work',t);self.assertNotIn('rsd0614-openwrt-v53-work',t);self.assertNotIn('rsd0614-openwrt-v52-work',t);self.assertIn('if (-not $HaveBuilder -or $RebuildBuilder)',t);self.assertNotIn('volume rm',t);self.assertNotIn('volume prune',t)
 def test_deep_audit_runs_before_candidate_result(self):
  t=(ROOT/'build-rsd0614-initramfs.sh').read_text();self.assertLess(t.index('"$PORT_DIR/deep_audit.py"'),t.index("echo 'COMPILE=PASS'"));self.assertIn('export_build_evidence.py',t)
 def test_v534_metadata_and_provenance_wiring(self):
  lock=json.loads((ROOT/'SOURCE_LOCK.json').read_text());self.assertEqual(lock['bundle_version'],'5.3.4');self.assertIn('direct NET/PCIe/WiFi IRQs masked',lock['intent']);self.assertIn('all enabled auto mount_root paths suppressed',lock['intent']);self.assertIn('default eth0/eth1 synthesis suppressed',lock['intent']);self.assertIn('UART RX/TX index 9',lock['intent'])
  build=(ROOT/'build-rsd0614-initramfs.sh').read_text();self.assertIn('PORT_INPUT_FINGERPRINT.txt',build);self.assertIn('--port-fingerprint',build);self.assertIn('--project-commit',build);self.assertIn('--builder-image-id',build)
  wrapper=(ROOT/'Build-RSD0614.ps1').read_text(encoding='utf-8-sig');self.assertIn('BUILDER_IMAGE_ID=',wrapper)
  workflow=(ROOT/'.github/workflows/build-initramfs.yml').read_text();self.assertIn('BUILDER_IMAGE_ID=',workflow);self.assertIn('PROJECT_COMMIT=$GITHUB_SHA',workflow)
class TreeTransactionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tree=self.root/'openwrt';self.tree.mkdir();self.audit=self.root/'audit';target=self.tree/'target/linux/realtek';(target/'base-files/etc/init.d').mkdir(parents=True);(target/'base-files/etc/init.d/dir842-asic').write_text('fixture old script');(target/'image').mkdir();(target/'image/Makefile').write_text('DEVICE_VARS += IMAGE_SIZE\ndefine Device/RSD0614\nendef\n');(target/'rtl8197f').mkdir();(target/'rtl8197f/config-4.14').write_text('CONFIG_NET_RTL819X=y\n');irq=target/'files-4.14/arch/mips/realtek/irq.c';irq.parent.mkdir(parents=True);irq.write_text(hs.IRQ_UNSAFE_BLOCK+'\n');boot=self.tree/'package/base-files/files/etc/init.d/boot';boot.parent.mkdir(parents=True);boot.write_text('#!/bin/sh /etc/rc.common\nboot() {\n'+hs.BOOT_MOUNT_ROOT_LINE+'\t/sbin/kmodloader\n}\n');defaultnet=self.tree/'package/base-files/files/etc/board.d/99-default_network';defaultnet.parent.mkdir(parents=True);defaultnet.write_text('. /lib/functions/uci-defaults.sh\nboard_config_update\n'+hs.DEFAULT_NETWORK_UNSAFE+'board_config_flush\n')
  def git(*a):return subprocess.check_output(['git','-C',str(self.tree),*a],text=True,stderr=subprocess.DEVNULL).strip()
  git('init','-q');git('add','.');git('-c','user.name=Fixture','-c','user.email=test@example.invalid','commit','-qm','fixture');self.head=git('rev-parse','HEAD');self.target=target
 def tearDown(self):self.tmp.cleanup()
 def test_real_filesystem_isolation(self):
  result=hs.harden(self.tree,ROOT,self.audit,expected=self.head);self.assertEqual({r['path'] for r in hs.tree_records(self.target/'base-files')},set(hs.BASE_FILES));self.assertIn(hs.IRQ_SAFE_BLOCK,(self.target/'files-4.14/arch/mips/realtek/irq.c').read_text());self.assertNotIn('mount_root',(self.tree/'package/base-files/files/etc/init.d/boot').read_text());self.assertNotIn("ucidef_set_interface_lan 'eth0'",(self.tree/'package/base-files/files/etc/board.d/99-default_network').read_text());self.assertTrue((Path(result['retained_source_backup'])/'etc/init.d/dir842-asic').exists());self.assertFalse((self.target/'base-files/etc/init.d/dir842-asic').exists());self.assertEqual((self.target/'base-files').stat().st_mode&0o777,0o755);hs.harden(self.tree,ROOT,self.audit,expected=self.head);self.assertEqual({r['path'] for r in hs.tree_records(self.target/'base-files')},set(hs.BASE_FILES))
 def test_bad_revision_no_mutation(self):
  before=hs.tree_records(self.target)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected='0'*40)
  self.assertEqual(hs.tree_records(self.target),before)
 def test_bad_anchor_no_mutation(self):
  (self.target/'image/Makefile').write_text('invalid');before=hs.tree_records(self.target)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.target),before)
 def test_bad_irq_anchor_no_mutation(self):
  irq=self.target/'files-4.14/arch/mips/realtek/irq.c';irq.write_text('unexpected irq source');before=hs.tree_records(self.tree)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.tree),before)
 def test_bad_boot_anchor_no_mutation(self):
  boot=self.tree/'package/base-files/files/etc/init.d/boot';boot.write_text('unexpected boot source');before=hs.tree_records(self.tree)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.tree),before)
 def test_bad_default_network_anchor_no_mutation(self):
  p=self.tree/'package/base-files/files/etc/board.d/99-default_network';p.write_text('unexpected default network source');before=hs.tree_records(self.tree)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.tree),before)
 def test_symlink_target_refused(self):
  original=self.target/'rtl8197f/config-4.14';original.unlink();external=self.root/'important';external.write_text('preserve');original.symlink_to(external)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(external.read_text(),'preserve')
 def test_backup_inside_source_refused(self):
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.tree/'audit',expected=self.head)
class ExportEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tree=self.root/'tree';self.out=self.root/'out';self.linux=self.tree/'build_dir/target-mipsel_24kc_musl/linux-realtek_rtl8197f/linux-4.14.187';self.linux.mkdir(parents=True);(self.linux/'.config').write_text('CONFIG_MTD_SPI_NOR=y\nCONFIG_SPI_SHEIPA=y\nCONFIG_SOC_RTL8197F=y\n')
  for n in ('System.map','vmlinux'):(self.linux/n).write_text('explicit fixture')
  for n in ('vmlinux-initramfs.elf','vmlinux-initramfs.debug'):(self.linux.parent/n).write_text('explicit fixture')
  src=self.linux/'drivers/mtd/spi-nor/spi-nor.c';src.parent.mkdir(parents=True);src.write_text('{ "bh25q64", INFO(0x684017, 0, 65536, 128, 0x2008) },');irq=self.linux/'arch/mips/realtek/irq.c';irq.parent.mkdir(parents=True);irq.write_text(hs.IRQ_SAFE_BLOCK+'\n');uart=self.linux/'include/uapi/linux/serial_reg.h';uart.parent.mkdir(parents=True);uart.write_text('#ifdef CONFIG_SOC_RTL8197F\n#define UART_RX 9\n#define UART_TX 9\n#else\n#define UART_RX 0\n#define UART_TX 0\n#endif\n');self.log=self.root/'build.log';self.log.write_text('BOARD="RSD0614" SUBTARGET="rtl8197f"\n')
 def tearDown(self):self.tmp.cleanup()
 def test_export_only_records_fixture_not_boot_success(self):
  from export_build_evidence import export;export(self.tree,self.out,self.log);manifest=json.loads((self.out/'kernel-evidence/manifest.json').read_text());self.assertEqual(len(manifest['files']),8);self.assertEqual(manifest['loader_board_values'],['RSD0614'])
 def test_export_records_provenance(self):
  from export_build_evidence import export;export(self.tree,self.out,self.log,port_fingerprint='a'*64,project_commit='b'*40,builder_image_id='sha256:'+'c'*64);manifest=json.loads((self.out/'kernel-evidence/manifest.json').read_text());self.assertEqual(manifest['provenance'],{'port_input_fingerprint':'a'*64,'project_commit':'b'*40,'builder_image_id':'sha256:'+'c'*64})
 def test_wrong_board_rejected(self):
  from export_build_evidence import export;self.log.write_text('BOARD="ACTIONRF1200" SUBTARGET="rtl8197f"\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_board_log_rejected(self):
  from export_build_evidence import export;self.log.write_text('no loader evidence')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_driver_survived_config_rejected(self):
  from export_build_evidence import export
  with (self.linux/'.config').open('a') as f:f.write('CONFIG_NET_RTL819X=y\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_spi_patch_rejected(self):
  from export_build_evidence import export;(self.linux/'drivers/mtd/spi-nor/spi-nor.c').write_text('not patched')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_uart_register_layout_rejected(self):
  from export_build_evidence import export;(self.linux/'include/uapi/linux/serial_reg.h').write_text('#define UART_RX 0\\n#define UART_TX 0\\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_irq_hardening_rejected(self):
  from export_build_evidence import export;(self.linux/'arch/mips/realtek/irq.c').write_text(hs.IRQ_UNSAFE_BLOCK+'\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_required_elf_rejected(self):
  from export_build_evidence import export;(self.linux.parent/'vmlinux-initramfs.elf').unlink()
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
if __name__=='__main__':unittest.main(verbosity=2)
