#!/usr/bin/env python3
"""
gen_modmap.py
Generate modules.json for vmp38_iat_rebuild.py from a live Win11 process.
Run ON the target machine with the dumped process still alive.

pip install pefile==2023.2.7

python gen_modmap.py <PID> -o modules.json
"""

import argparse
import ctypes
import ctypes.wintypes as w
import json
import sys
from pathlib import Path

import pefile  # ==2023.2.7

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
LIST_MODULES_ALL = 0x03

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", w.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


def enum_modules(pid: int) -> list[tuple[int, int, str]]:
    hproc = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not hproc:
        raise OSError(f"OpenProcess failed: {ctypes.get_last_error():#x}")

    try:
        hmod_array = (ctypes.c_void_p * 1024)()
        cb_needed = w.DWORD()
        if not psapi.EnumProcessModulesEx(
            hproc,
            ctypes.byref(hmod_array),
            ctypes.sizeof(hmod_array),
            ctypes.byref(cb_needed),
            LIST_MODULES_ALL,
        ):
            raise OSError(f"EnumProcessModulesEx failed: {ctypes.get_last_error():#x}")

        count = cb_needed.value // ctypes.sizeof(ctypes.c_void_p)
        results = []
        for i in range(count):
            hmod = hmod_array[i]
            name_buf = ctypes.create_unicode_buffer(260)
            psapi.GetModuleFileNameExW(hproc, hmod, name_buf, 260)

            mi = MODULEINFO()
            psapi.GetModuleInformation(hproc, hmod, ctypes.byref(mi), ctypes.sizeof(mi))

            results.append((mi.lpBaseOfDll, mi.SizeOfImage, name_buf.value))
        return results
    finally:
        kernel32.CloseHandle(hproc)


def parse_exports(dll_path: str, base: int) -> dict[str, str]:
    try:
        pe = pefile.PE(dll_path, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    except Exception:
        return {}

    exports = {}
    if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        return exports

    for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if exp.name:
            name = exp.name.decode("ascii", errors="replace")
            addr = base + exp.address
            exports[name] = f"{addr:#x}"
    return exports


def main():
    ap = argparse.ArgumentParser(description="generate module map from live process")
    ap.add_argument("pid", type=int)
    ap.add_argument("-o", "--output", default="modules.json")
    args = ap.parse_args()

    modules = enum_modules(args.pid)
    result = {}

    for base, size, path in modules:
        dll_name = Path(path).name.lower()
        print(f"[*] {dll_name} @ {base:#x} size {size:#x}")
        exports = parse_exports(path, base)
        result[dll_name] = {
            "base": f"{base:#x}",
            "size": f"{size:#x}",
            "exports": exports,
        }

    Path(args.output).write_text(json.dumps(result, indent=2))
    print(f"[*] wrote {args.output}: {len(result)} modules")


if __name__ == "__main__":
    main()
