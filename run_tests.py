#!/usr/bin/env python3
from pathlib import Path
import sys,unittest
if __name__=='__main__':
    root=Path(__file__).resolve().parent;sys.path.insert(0,str(root));from runtime_info import runtime_info;import json;print('TEST_RUNTIME: '+json.dumps(runtime_info(),sort_keys=True),flush=True);suite=unittest.defaultTestLoader.discover(str(root),pattern='test_*.py');result=unittest.TextTestRunner(verbosity=2).run(suite);print(f'LOCAL_REGRESSION: {result.testsRun} tests; failures={len(result.failures)}; errors={len(result.errors)}');print('DOCKER_APT_INSTALL: NOT TESTED by this suite');print('OPENWRT_COMPILE_AND_RAM_BOOT: NOT TESTED by this suite');raise SystemExit(0 if result.wasSuccessful() else 1)
