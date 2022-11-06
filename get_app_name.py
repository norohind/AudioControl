import ctypes
from ctypes import wintypes as w
import array
from functools import lru_cache
from psutil import Process
import traceback


ver = ctypes.WinDLL('version')
ver.GetFileVersionInfoSizeW.argtypes = w.LPCWSTR, w.LPDWORD
ver.GetFileVersionInfoSizeW.restype = w.DWORD
ver.GetFileVersionInfoW.argtypes = w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID
ver.GetFileVersionInfoW.restype = w.BOOL
ver.VerQueryValueW.argtypes = w.LPCVOID, w.LPCWSTR, ctypes.POINTER(w.LPVOID), w.PUINT
ver.VerQueryValueW.restype = w.BOOL


def get_file_description(filepath: str) -> str:
    # https://stackoverflow.com/questions/42604493/verqueryvaluew-issue-python-3
    size = ver.GetFileVersionInfoSizeW(filepath, None)
    if not size:
        raise RuntimeError('version info not found')

    res = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(filepath, 0, size, res):
        raise RuntimeError('GetFileVersionInfoW failed')

    buf = w.LPVOID()
    length = w.UINT()
    # Look for codepages
    if not ver.VerQueryValueW(res, r'\VarFileInfo\Translation', ctypes.byref(buf), ctypes.byref(length)):
        raise RuntimeError('VerQueryValueW failed to find translation')

    if length.value == 0:
        raise RuntimeError('no code pages')

    codepages = array.array('H', ctypes.string_at(buf.value, length.value))
    codepage = codepages[:2]
    # Extract information
    if not ver.VerQueryValueW(
        res,
        rf'\StringFileInfo\{codepage[0]:04x}{codepage[1]:04x}\FileDescription',
        ctypes.byref(buf),
        ctypes.byref(length)
    ):
        raise RuntimeError('VerQueryValueW failed to find file version')

    return ctypes.wstring_at(buf.value, length.value - 1)


@lru_cache
def get_app_name(app_process: Process) -> str:
    try:
        return get_file_description(app_process.exe())

    except Exception:
        traceback.print_exc()
        return app_process.name()
