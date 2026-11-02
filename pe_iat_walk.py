#!/usr/bin/env python3
"""Walk PE32+ import directory, resolve each slot via target module export table."""

import struct
import sys
import os

DOS_MAGIC = 0x5A4D
NT_SIG = 0x00004550
PE32PLUS = 0x20B
ORD_FLAG64 = 1 << 63
DD_IMPORT = 1
DD_EXPORT = 0


def fatal(msg):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def u16(data, off):
    if off + 2 > len(data):
        fatal(f"truncated u16 at 0x{off:x}")
    return struct.unpack_from("<H", data, off)[0]


def u32(data, off):
    if off + 4 > len(data):
        fatal(f"truncated u32 at 0x{off:x}")
    return struct.unpack_from("<I", data, off)[0]


def u64(data, off):
    if off + 8 > len(data):
        fatal(f"truncated u64 at 0x{off:x}")
    return struct.unpack_from("<Q", data, off)[0]


def cstr(data, off):
    end = data.index(b"\x00", off)
    return data[off:end].decode("ascii", errors="replace")


def sections(data, nt_off, num_sec, opt_size):
    sec_off = nt_off + 24 + opt_size
    out = []
    for i in range(num_sec):
        base = sec_off + i * 40
        vsize = u32(data, base + 8)
        va = u32(data, base + 12)
        raw_sz = u32(data, base + 16)
        raw_ptr = u32(data, base + 20)
        out.append((va, vsize, raw_sz, raw_ptr))
    return out


def rva2off(secs, rva):
    for va, vsize, raw_sz, raw_ptr in secs:
        if va <= rva < va + max(vsize, raw_sz):
            return rva - va + raw_ptr
    return None


def parse_exports(data, secs):
    """Return (by_name, by_ordinal) from export directory.
    by_name:    {name: (ordinal, forwarder|None)}
    by_ordinal: {ordinal: (name|None, forwarder|None)}
    """
    nt_off = u32(data, 0x3C)
    opt_off = nt_off + 24
    magic = u16(data, opt_off)
    if magic == PE32PLUS:
        ndd = u32(data, opt_off + 108)
        dd_base = opt_off + 112
    elif magic == 0x10B:
        ndd = u32(data, opt_off + 92)
        dd_base = opt_off + 96
    else:
        return {}, {}
    if ndd < 1:
        return {}, {}

    exp_rva = u32(data, dd_base)
    exp_size = u32(data, dd_base + 4)
    if exp_rva == 0:
        return {}, {}

    eo = rva2off(secs, exp_rva)
    if eo is None:
        return {}, {}

    ord_base = u32(data, eo + 16)
    num_funcs = u32(data, eo + 20)
    num_names = u32(data, eo + 24)
    addr_rva = u32(data, eo + 28)
    nameptr_rva = u32(data, eo + 32)
    ordtab_rva = u32(data, eo + 36)

    addr_o = rva2off(secs, addr_rva)
    np_o = rva2off(secs, nameptr_rva)
    ot_o = rva2off(secs, ordtab_rva)
    if any(x is None for x in (addr_o, np_o, ot_o)):
        return {}, {}

    func_rvas = [u32(data, addr_o + i * 4) for i in range(num_funcs)]

    def is_fwd(rva):
        return exp_rva <= rva < exp_rva + exp_size

    def fwd_str(rva):
        fo = rva2off(secs, rva)
        return cstr(data, fo) if fo is not None else None

    by_name = {}
    by_ordinal = {}

    for i in range(num_names):
        nrva = u32(data, np_o + i * 4)
        oidx = u16(data, ot_o + i * 2)
        no = rva2off(secs, nrva)
        if no is None:
            continue
        name = cstr(data, no)
        ordinal = oidx + ord_base
        frva = func_rvas[oidx] if oidx < num_funcs else 0
        fwd = fwd_str(frva) if is_fwd(frva) else None
        by_name[name] = (ordinal, fwd)
        by_ordinal[ordinal] = (name, fwd)

    for i in range(num_funcs):
        ordinal = i + ord_base
        if ordinal not in by_ordinal:
            frva = func_rvas[i]
            fwd = fwd_str(frva) if is_fwd(frva) else None
            by_ordinal[ordinal] = (None, fwd)

    return by_name, by_ordinal


def load_module(name, search_dirs):
    low = name.lower()
    for d in search_dirs:
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for e in entries:
            if e.lower() == low and os.path.isfile(os.path.join(d, e)):
                path = os.path.join(d, e)
                with open(path, "rb") as f:
                    raw = f.read()
                if len(raw) < 64 or u16(raw, 0) != DOS_MAGIC:
                    continue
                nt = u32(raw, 0x3C)
                if nt + 24 > len(raw) or u32(raw, nt) != NT_SIG:
                    continue
                opt_sz = u16(raw, nt + 20)
                num_s = u16(raw, nt + 6)
                secs = sections(raw, nt, num_s, opt_sz)
                return parse_exports(raw, secs)
    return None, None


def validate_pe(data):
    if len(data) < 64:
        fatal("file too small for DOS header")
    if u16(data, 0) != DOS_MAGIC:
        fatal(f"bad DOS magic: 0x{u16(data, 0):04X}")
    nt_off = u32(data, 0x3C)
    if nt_off + 264 > len(data):
        fatal(f"e_lfanew 0x{nt_off:x} points past EOF")
    if u32(data, nt_off) != NT_SIG:
        fatal(f"bad NT signature: 0x{u32(data, nt_off):08X}")
    opt_off = nt_off + 24
    magic = u16(data, opt_off)
    if magic != PE32PLUS:
        fatal(f"not PE32+: optional header magic 0x{magic:04X}")
    return nt_off


def main():
    if len(sys.argv) < 2:
        fatal("usage: pe_iat_walk.py <pe_file> [module_search_dir ...]")

    path = sys.argv[1]
    extra_dirs = sys.argv[2:]

    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        fatal(f"cannot open {path}: {e}")

    nt_off = validate_pe(data)
    num_sec = u16(data, nt_off + 6)
    opt_size = u16(data, nt_off + 20)
    opt_off = nt_off + 24
    secs = sections(data, nt_off, num_sec, opt_size)

    ndd = u32(data, opt_off + 108)
    dd_base = opt_off + 112
    if ndd <= DD_IMPORT:
        fatal("no import data directory")
    imp_rva = u32(data, dd_base + DD_IMPORT * 8)
    imp_size = u32(data, dd_base + DD_IMPORT * 8 + 4)
    if imp_rva == 0:
        fatal("import directory RVA is zero")

    search_dirs = [os.path.dirname(os.path.abspath(path))] + extra_dirs

    # module export cache
    mod_cache = {}

    imp_off = rva2off(secs, imp_rva)
    if imp_off is None:
        fatal(f"cannot map import directory RVA 0x{imp_rva:x}")

    desc_idx = 0
    while True:
        base = imp_off + desc_idx * 20
        if base + 20 > len(data):
            break
        oft_rva = u32(data, base)       # OriginalFirstThunk
        name_rva = u32(data, base + 12)
        ft_rva = u32(data, base + 16)   # FirstThunk
        if oft_rva == 0 and name_rva == 0 and ft_rva == 0:
            break

        name_o = rva2off(secs, name_rva)
        if name_o is None:
            fatal(f"cannot map module name RVA 0x{name_rva:x}")
        mod_name = cstr(data, name_o)

        # load target module exports for forwarder detection
        if mod_name not in mod_cache:
            bn, bo = load_module(mod_name, search_dirs)
            mod_cache[mod_name] = (bn or {}, bo or {})
        exp_by_name, exp_by_ord = mod_cache[mod_name]

        # prefer OriginalFirstThunk; fall back to FirstThunk
        thunk_rva = oft_rva if oft_rva != 0 else ft_rva
        thunk_off = rva2off(secs, thunk_rva)
        if thunk_off is None:
            fatal(f"cannot map thunk RVA 0x{thunk_rva:x} for {mod_name}")

        ft_off = rva2off(secs, ft_rva) if ft_rva != 0 else None
        slot_idx = 0
        while True:
            entry = u64(data, thunk_off + slot_idx * 8)
            if entry == 0:
                break

            ft_va = ft_rva + slot_idx * 8 if ft_rva else 0

            if entry & ORD_FLAG64:
                ordinal = entry & 0xFFFF
                exp_info = exp_by_ord.get(ordinal)
                if exp_info and exp_info[1]:
                    print(f"{mod_name}  ORDINAL {ordinal}  FORWARDER {exp_info[1]}  [FT RVA 0x{ft_va:x}]")
                else:
                    print(f"{mod_name}  ORDINAL {ordinal}  [FT RVA 0x{ft_va:x}]")
            else:
                hint_off = rva2off(secs, entry & 0x7FFFFFFFFFFFFFFF)
                if hint_off is None:
                    fatal(f"cannot map hint/name RVA 0x{entry:x}")
                hint = u16(data, hint_off)
                func_name = cstr(data, hint_off + 2)
                exp_info = exp_by_name.get(func_name)
                if exp_info and exp_info[1]:
                    print(f"{mod_name}  {func_name}  FORWARDER {exp_info[1]}  [hint {hint} FT RVA 0x{ft_va:x}]")
                else:
                    print(f"{mod_name}  {func_name}  [hint {hint} FT RVA 0x{ft_va:x}]")

            slot_idx += 1

        desc_idx += 1


if __name__ == "__main__":
    main()
