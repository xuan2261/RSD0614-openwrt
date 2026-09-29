"""Local regressions. These tests do not compile OpenWrt or contact a router."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,tempfile,unittest
import apply_rsd0614_profile as profile
import check_config
import verify_rsd0614_initramfs as screen_module
ROOT=Path(__file__).resolve().parent
ANCHOR='# dedicated test fixture\ndefine Device/GWR1200AC\n  DEVICE_TITLE := Fixture\nendef\n'
NAME='openwrt-RSD0614-initramfs-kernel.bin';GOOD_CONFIG='CONFIG_TARGET_realtek_rtl8197f_DEVICE_RSD0614=y\nCONFIG_TARGET_ROOTFS_INITRAMFS=y\n'
class ProfileTests(unittest.TestCase):
 def test_01_comment_words_are_not_pipelines(self):self.assertIn('factory.bin',profile.DEVICE_BLOCK);profile.validate_profile(profile.DEVICE_BLOCK)
 def test_02_real_factory_directive_is_rejected(self):
  with self.assertRaises(ValueError):profile.validate_profile(profile.DEVICE_BLOCK.replace('  IMAGES :=','  IMAGE/factory.bin := append-kernel\n  IMAGES :='))
 def test_03_real_sysupgrade_directive_is_rejected(self):
  with self.assertRaises(ValueError):profile.validate_profile(profile.DEVICE_BLOCK.replace('  IMAGES :=','  IMAGE/sysupgrade.bin := append-kernel\n  IMAGES :='))
 def test_04_nonempty_images_rejected(self):
  with self.assertRaises(ValueError):profile.validate_profile(profile.DEVICE_BLOCK.replace('IMAGES :=','IMAGES := payload.bin'))
 def test_05_append_images_rejected(self):
  with self.assertRaises(ValueError):profile.validate_profile(profile.DEVICE_BLOCK.replace('IMAGES :=','IMAGES += payload.bin'))
 def test_06_wrong_parent_rejected(self):
  with self.assertRaises(ValueError):profile.validate_profile(profile.DEVICE_BLOCK.replace('Device/RealtekDTS','Device/GWR1200AC'))
 def test_07_nonempty_device_packages_rejected(self):
  with self.assertRaises(ValueError):profile.validate_profile(profile.DEVICE_BLOCK.replace('DEVICE_PACKAGES :=','DEVICE_PACKAGES := kmod-rtw88'))
 def test_08_patch_is_idempotent(self):
  once=profile.patch_text(ANCHOR);self.assertEqual(profile.patch_text(once),once);self.assertEqual(once.count('define Device/RSD0614'),1)
 def test_09_unknown_anchor_rejected(self):
  with self.assertRaises(ValueError):profile.patch_text('define Device/OTHER\nendef\n')
 def test_10_existing_different_profile_rejected(self):
  text=profile.patch_text(ANCHOR).replace('IMAGE_SIZE := 7808k','IMAGE_SIZE := 9999k')
  with self.assertRaises(ValueError):profile.patch_text(text)
 def test_11_malformed_existing_profile_rejected(self):
  with self.assertRaises(ValueError):profile.patch_text('define Device/RSD0614\n'+ANCHOR)
class GitFixtureTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.repo=Path(self.temp.name)/'repo';self.port=Path(self.temp.name)/'port';self.port.mkdir();(self.port/'RSD0614.dts').write_bytes((ROOT/'RSD0614.dts').read_bytes());self.mk=self.repo/'files/target/linux/realtek/image/Makefile';self.mk.parent.mkdir(parents=True);self.mk.write_text(ANCHOR)
  def git(*args):return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.DEVNULL,text=True).strip()
  git('init','-q');git('add','.');git('-c','user.name=Test Fixture','-c','user.email=test@example.invalid','commit','-qm','fixture');self.head=git('rev-parse','HEAD');self.dest=self.repo/'files/target/linux/realtek/dts/RSD0614.dts'
 def tearDown(self):self.temp.cleanup()
 def test_12_apply_executes_on_real_temporary_git_repo(self):profile.apply_profile(self.repo,self.port,expected_commit=self.head);self.assertEqual(self.dest.read_bytes(),(ROOT/'RSD0614.dts').read_bytes());once=self.mk.read_bytes();profile.apply_profile(self.repo,self.port,expected_commit=self.head);self.assertEqual(self.mk.read_bytes(),once)
 def test_13_bad_revision_does_not_write(self):
  original=self.mk.read_bytes()
  with self.assertRaises(ValueError):profile.apply_profile(self.repo,self.port,expected_commit='0'*40)
  self.assertEqual(original,self.mk.read_bytes());self.assertFalse(self.dest.exists())
 def test_14_bad_anchor_does_not_copy_dts(self):
  self.mk.write_text('NOT THE EXPECTED SOURCE\n')
  with self.assertRaises(ValueError):profile.apply_profile(self.repo,self.port,expected_commit=self.head)
  self.assertFalse(self.dest.exists())
 def test_15_different_existing_dts_is_preserved(self):
  self.dest.parent.mkdir(parents=True);self.dest.write_text('important existing file')
  with self.assertRaises(ValueError):profile.apply_profile(self.repo,self.port,expected_commit=self.head)
  self.assertEqual(self.dest.read_text(),'important existing file');self.assertEqual(self.mk.read_text(),ANCHOR)
class ConfigTests(unittest.TestCase):
 def test_16_minimal_config(self):check_config.validate(GOOD_CONFIG)
 def test_17_missing_target(self):
  with self.assertRaises(ValueError):check_config.validate('CONFIG_TARGET_ROOTFS_INITRAMFS=y\n')
 def test_18_wifi_module_rejected_not_only_builtin(self):
  with self.assertRaises(ValueError):check_config.validate(GOOD_CONFIG+'CONFIG_PACKAGE_kmod-rtl8192cd=m\n')
 def test_19_extra_target_rejected(self):
  with self.assertRaises(ValueError):check_config.validate(GOOD_CONFIG+'CONFIG_TARGET_realtek_rtl8197f_DEVICE_GWR1200AC_V1=y\n')
 def test_20_persistent_fs_rejected(self):
  with self.assertRaises(ValueError):check_config.validate(GOOD_CONFIG+'CONFIG_TARGET_ROOTFS_SQUASHFS=y\n')
 def test_21_broad_target_selection_rejected(self):
  with self.assertRaises(ValueError):check_config.validate(GOOD_CONFIG+'CONFIG_TARGET_ALL=y\n')
 def test_22_initramfs_compression_allowed(self):check_config.validate(GOOD_CONFIG+'CONFIG_TARGET_ROOTFS_INITRAMFS_COMPRESSION_NONE=y\n')
class ArtifactScreenTests(unittest.TestCase):
 def test_23_zero_blob_rejected(self):self.assertTrue(screen_module.screen(bytes(65536),NAME))
 def test_24_ff_blob_rejected(self):self.assertTrue(screen_module.screen(b'\xff'*65536,NAME))
 def test_25_container_header_rejected(self):
  for signature in (b'cr6c',b'cr6b',bytes.fromhex('27051956')):self.assertTrue(screen_module.screen(signature+bytes(65536),NAME))
 def test_26_size_boundaries_rejected(self):self.assertTrue(screen_module.screen(b'abc',NAME));self.assertTrue(screen_module.screen(b'AB'*(0x800000+1),NAME))
 def test_27_wrong_filename_rejected(self):self.assertTrue(screen_module.screen(bytes(range(256))*256,'other-device.bin'))
 def test_28_pass_is_screen_only_no_boot_authority(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/NAME;p.write_bytes(bytes(range(256))*256);run=subprocess.run([sys.executable,str(ROOT/'verify_rsd0614_initramfs.py'),str(p)],capture_output=True,text=True);self.assertEqual(run.returncode,0);self.assertIn('ARTIFACT_SCREEN: PASS',run.stdout);self.assertIn('RAM_BOOT_AUTHORIZED: NO',run.stdout);self.assertIn('BOOT_QUALIFICATION: NOT YET VERIFIED',run.stdout)
class PackagingTests(unittest.TestCase):
 def test_29_snapshot_sources_render_without_side_effects(self):
  p=subprocess.run(['sh',str(ROOT/'apt-bootstrap.sh'),'--print-sources','20260901T000000Z','https'],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(len(p.stdout.splitlines()),3);self.assertEqual(p.stdout.count('20260901T000000Z'),3);self.assertEqual(p.stdout.count('signed-by=/usr/share/keyrings/debian-archive-keyring.gpg'),3);self.assertNotIn('deb.debian.org',p.stdout)
 def test_30_bad_snapshot_injection_rejected(self):
  p=subprocess.run(['sh',str(ROOT/'apt-bootstrap.sh'),'--print-sources','bad;echo x','https'],capture_output=True,text=True);self.assertNotEqual(p.returncode,0);self.assertEqual(p.stdout,'')
 def test_31_shell_syntax(self):
  for shell,name in [('sh','apt-bootstrap.sh'),('bash','build-rsd0614-initramfs.sh')]:
   p=subprocess.run([shell,'-n',str(ROOT/name)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
 def test_32_signature_verification_not_disabled(self):
  t=(ROOT/'apt-bootstrap.sh').read_text()
  for token in ('trusted=yes','--allow-unauthenticated','Verify-Peer "false"','AllowInsecureRepositories "true"'):self.assertNotIn(token,t)
  self.assertIn('apt-get --error-on=any update',t)
 def test_33_dts_fixed_partitions_exact_and_read_only(self):
  t=(ROOT/'RSD0614.dts').read_text();parts=re.findall(r'partition@[0-9a-f]+\s*\{(.*?)\};',t,re.S);self.assertEqual(len(parts),6);actual=[]
  for part in parts:
   self.assertIn('read-only;',part);m=re.search(r'reg = <(0x[0-9a-f]+) (0x[0-9a-f]+)>;',part);actual.append(tuple(int(n,16) for n in m.groups()))
  self.assertEqual(actual,[(0,0x20000),(0x20000,0x10000),(0x30000,0x7a0000),(0x7d0000,0x10000),(0x7e0000,0x10000),(0x7f0000,0x10000)])
 def test_34_dts_peripherals_explicitly_disabled(self):
  t=(ROOT/'RSD0614.dts').read_text()
  for label in ('pcie0','pcie1','wmac','ethernet'):self.assertRegex(t,rf'&{label}\s*\{{\s*status = "disabled";\s*\}};')
 def test_34b_dts_console_probe_keeps_bootconsole(self):
  t=(ROOT/'RSD0614.dts').read_text();self.assertIn('bootargs = "console=ttyS0,115200 initcall_debug ignore_loglevel keep_bootcon";',t)
 def test_35_source_commit_locks_preserved(self):
  lock=json.loads((ROOT/'SOURCE_LOCK.json').read_text());self.assertEqual(lock['donor_commit'],profile.EXPECTED_DONOR_COMMIT);self.assertEqual(lock['base_commit'],'8a0ccb93f3431bcf8f5c5d03d4acc2c8e442de67');self.assertFalse(lock['ram_boot_authorized'])
 def test_36_build_files_have_no_router_transport_or_flash_commands(self):
  for name in ('Build-RSD0614.ps1','build-rsd0614-initramfs.sh'):
   text=(ROOT/name).read_text()
   for token in ('tftp ','FLW ','AUTOBURN 1','ERASECHIP','ERASESECTOR','mtd write'):self.assertNotIn(token,text)
 def test_37_wrapper_preserves_logs_and_uses_dedicated_volume(self):
  t=(ROOT/'Build-RSD0614.ps1').read_text();self.assertIn('--progress=plain',t);self.assertIn('Tee-Object -FilePath',t);self.assertIn('type=volume,source=$Volume,target=/work',t);self.assertNotIn('Remove-Item',t);self.assertNotIn('volume prune',t);self.assertIn('$BuilderOnly',t)
if __name__=='__main__':unittest.main(verbosity=2)
