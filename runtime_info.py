#!/usr/bin/env python3
import ctypes,json,platform,sys,_lzma
def runtime_info():
    result={'python':platform.python_version(),'python_executable':sys.executable,'platform':platform.system(),'lzma_extension':_lzma.__file__,'linked_liblzma':'UNAVAILABLE','version_probe':'NOT_AVAILABLE'}
    try:
        lib=ctypes.CDLL(_lzma.__file__);version=lib.lzma_version_string;version.argtypes=[];version.restype=ctypes.c_char_p;value=version()
        if value:result['linked_liblzma']=value.decode('ascii');result['version_probe']='RESOLVED_FROM_PYTHON_EXTENSION'
    except (AttributeError,OSError,UnicodeError) as exc:result['version_probe']=type(exc).__name__
    return result
if __name__=='__main__':print(json.dumps(runtime_info(),sort_keys=True))
