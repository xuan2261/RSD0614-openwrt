"""Real decode tests for old/new liblzma; no skip or mock of the decoder."""
from pathlib import Path
import hashlib,lzma,struct,tempfile,unittest
import deep_audit as da
from lzma_test_fixture import load_fixture,payload_bytes,FIXTURE_SHA256,PAYLOAD_SHA256
ROOT=Path(__file__).resolve().parent
def image_for(stream,offset=1024,tail=b'\x00'*65536):return bytes(offset)+bytes(stream)+tail
class LzmaCompatibilityTests(unittest.TestCase):
 def test_fixture_digest_and_header(self):
  data=load_fixture();self.assertEqual(len(data),344);self.assertEqual(hashlib.sha256(data).hexdigest(),FIXTURE_SHA256);self.assertEqual(data[0],93);self.assertEqual(struct.unpack_from('<I',data,1)[0],1<<23);self.assertEqual(struct.unpack_from('<Q',data,5)[0],76822);self.assertEqual(hashlib.sha256(payload_bytes()).hexdigest(),PAYLOAD_SHA256)
 def test_direct_decode_eof_and_exact_payload(self):
  decoder=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE,memlimit=128<<20);result=decoder.decompress(load_fixture(),max_length=len(payload_bytes())+1);self.assertTrue(decoder.eof);self.assertEqual(result,payload_bytes());self.assertEqual(decoder.unused_data,b'')
 def test_production_decoder_preserves_nonpadding_trailer(self):
  tail=b'NON_PADDING_TRAILER'+bytes(65536);result,info=da.unpack_lzma(image_for(load_fixture(),tail=tail));self.assertEqual(result,payload_bytes());self.assertEqual(info['stream_consumed'],344);self.assertEqual(info['trailing_bytes'],len(tail))
 def test_candidate_at_zero(self):
  result,info=da.unpack_lzma(image_for(load_fixture(),offset=0));self.assertEqual(result,payload_bytes());self.assertEqual(info['stream_offset'],0)
 def test_last_scanned_offset(self):
  result,info=da.unpack_lzma(image_for(load_fixture(),offset=65535));self.assertEqual(result,payload_bytes());self.assertEqual(info['stream_offset'],65535)
 def test_offset_past_scan_window_rejected(self):
  with self.assertRaisesRegex(ValueError,'found 0'):da.unpack_lzma(image_for(load_fixture(),offset=65536))
 def test_two_valid_streams_rejected_as_ambiguous(self):
  stream=load_fixture();image=bytes(1024)+stream+bytes(100)+stream+bytes(65536)
  with self.assertRaisesRegex(ValueError,'found 2'):da.unpack_lzma(image)
 def test_unknown_decoded_size_rejected(self):
  stream=bytearray(load_fixture());stream[5:13]=b'\xff'*8
  with self.assertRaisesRegex(ValueError,'found 0'):da.unpack_lzma(image_for(stream))
 def test_decoded_size_out_of_budget_rejected(self):
  for size in (0,65535,da.MAX_OUTPUT+1):
   with self.subTest(size=size):
    stream=bytearray(load_fixture());stream[5:13]=struct.pack('<Q',size)
    with self.assertRaises(ValueError):da.unpack_lzma(image_for(stream))
 def test_inconsistent_size_without_padding_rejected(self):
  for size in (len(payload_bytes())-1,len(payload_bytes())+1):
   with self.subTest(size=size):
    stream=bytearray(load_fixture());stream[5:13]=struct.pack('<Q',size)
    with self.assertRaises(ValueError):da.unpack_lzma(image_for(stream,offset=65535,tail=b''))
 def test_truncated_compressed_payload_rejected(self):
  for cut in (13,40,170):
   with self.subTest(cut=cut),self.assertRaises(ValueError):da.unpack_lzma(image_for(load_fixture()[:cut],tail=b'\xff'*65536))
 def test_invalid_range_coder_header_rejected(self):
  stream=bytearray(load_fixture());stream[13]=0xff
  with self.assertRaises(ValueError):da.unpack_lzma(image_for(stream))
 def test_invalid_properties_rejected(self):
  stream=bytearray(load_fixture());stream[0]=0xff
  with self.assertRaises(ValueError):da.unpack_lzma(image_for(stream))
 def test_dictionary_budget_unchanged(self):
  stream=bytearray(load_fixture());stream[1:5]=struct.pack('<I',1<<25)
  with self.assertRaises(ValueError):da.unpack_lzma(image_for(stream))
 def test_short_and_empty_inputs_rejected(self):
  for data in (b'',load_fixture(),bytes(65535)):
   with self.subTest(size=len(data)),self.assertRaises(ValueError):da.unpack_lzma(data)
 def test_missing_fixture_does_not_skip(self):
  with tempfile.TemporaryDirectory() as directory:
   with self.assertRaises(FileNotFoundError):load_fixture(Path(directory)/'missing.lzma')
 def test_modified_fixture_does_not_skip(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'damaged.lzma';data=bytearray(load_fixture());data[-1]^=1;path.write_bytes(data)
   with self.assertRaisesRegex(ValueError,'integrity mismatch'):load_fixture(path)
 def test_runtime_version_is_diagnostic_only(self):
  from runtime_info import runtime_info;info=runtime_info();self.assertTrue(info['python']);self.assertTrue(info['linked_liblzma']);self.assertNotIn('BOOT_QUALIFICATION',info)
 def test_preflight_wrapper_has_no_compile_or_volume_mutation(self):
  source=(ROOT/'Test-RSD0614.ps1').read_text(encoding='utf-8-sig');self.assertIn('--network=none',source);self.assertIn('target=/port,readonly',source);self.assertIn('/port/run_tests.py',source);self.assertIn('if ($Code -ne 0)',source);self.assertNotIn('volume rm',source);self.assertNotIn('docker build',source);self.assertNotIn('build-rsd0614-initramfs.sh',source)
