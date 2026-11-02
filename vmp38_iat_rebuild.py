#!/usr/bin/env python3
"""
vmp38_iat_rebuild.py
IAT reconstructor for VMProtect 3.8 x64 PE dumps.
Target: PE x64, MSVC 19.4x, VMP 3.8, .vmp0 section, live dump, Win11 23H2.

pip install pefile==2023.2.7 capstone==5.0.3

python -I vmp38_iat_rebuild.py dump.exe modules.json -o rebuilt.exe
"""

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pefile  # ==2023.2.7
from capstone import (  # ==5.0.3
    Cs,
    CS_ARCH_X86,
    CS_MODE_64,
    CS_GRP_JUMP,
    CS_GRP_RET,
    CsInsn,
)
from capstone.x86 import (
    X86_OP_IMM,
    X86_OP_MEM,
    X86_REG_RAX,
    X86_REG_RBX,
    X86_REG_RCX,
    X86_REG_RDX,
    X86_REG_RIP,
    X86_REG_RSP,
)

TRAMPOLINE_STUB_SIZE = 14  # FF 25 00 00 00 00 + 8-byte addr
MAX_THUNK_INSNS = 32
CALL_REL32_OP = 0xE8
JMP_REL32_OP = 0xE9
FF_INDIRECT_CALL = bytes([0xFF, 0x15])
FF_INDIRECT_JMP = bytes([0xFF, 0x25])
IMAGE_DIRECTORY_ENTRY_IMPORT = 1
IMPORT_DESC_SIZE = 20
HINT_NAME_ALIGN = 2


@dataclass
class ResolvedImport:
    dll: str
    name: str
    ordinal: int
    api_addr: int


@dataclass
class CallSite:
    rva: int
    size: int  # 5 for E8/E9, 6 for FF15/FF25
    is_indirect: bool
    target_rva: int  # thunk RVA in .vmp0
    iat_slot_rva: Optional[int]  # for FF15/FF25, RVA of the pointer slot


@dataclass
class PatchEntry:
    call_site: CallSite
    resolved: ResolvedImport
    new_iat_slot_rva: int


class ModuleMap:
    def __init__(self, path: str):
        with open(path, "r") as f:
            raw = json.load(f)
        self._addr_to_api: dict[int, tuple[str, str, int]] = {}
        self._ranges: list[tuple[int, int, str]] = []
        for dll_name, info in raw.items():
            base = int(info["base"], 16)
            size = int(info.get("size", "0x100000"), 16)
            self._ranges.append((base, base + size, dll_name.lower()))
            for api_name, addr_str in info["exports"].items():
                addr = int(addr_str, 16)
                ordinal = info.get("ordinals", {}).get(api_name, 0)
                self._addr_to_api[addr] = (dll_name, api_name, ordinal)

    def resolve(self, addr: int) -> Optional[ResolvedImport]:
        hit = self._addr_to_api.get(addr)
        if hit:
            return ResolvedImport(dll=hit[0], name=hit[1], ordinal=hit[2], api_addr=addr)
        for lo, hi, dll in self._ranges:
            if lo <= addr < hi:
                offset = addr - lo
                return ResolvedImport(
                    dll=dll, name=f"__ordinal_{offset:#x}", ordinal=0, api_addr=addr
                )
        return None

    def is_module_addr(self, addr: int) -> bool:
        for lo, hi, _ in self._ranges:
            if lo <= addr < hi:
                return True
        return False


class ThunkResolver:
    def __init__(self, pe: pefile.PE, vmp_rva: int, vmp_size: int, image_base: int):
        self._pe = pe
        self._vmp_rva = vmp_rva
        self._vmp_size = vmp_size
        self._base = image_base
        self._md = Cs(CS_ARCH_X86, CS_MODE_64)
        self._md.detail = True
        self._cache: dict[int, Optional[int]] = {}

    def _rva_to_offset(self, rva: int) -> Optional[int]:
        try:
            return self._pe.get_offset_from_rva(rva)
        except pefile.PEFormatError:
            return None

    def _read_qword(self, rva: int) -> Optional[int]:
        off = self._rva_to_offset(rva)
        if off is None or off + 8 > len(self._pe.__data__):
            return None
        return struct.unpack_from("<Q", self._pe.__data__, off)[0]

    def _read_bytes(self, rva: int, size: int) -> Optional[bytes]:
        off = self._rva_to_offset(rva)
        if off is None or off + size > len(self._pe.__data__):
            return None
        return self._pe.__data__[off : off + size]

    def resolve(self, thunk_rva: int) -> Optional[int]:
        if thunk_rva in self._cache:
            return self._cache[thunk_rva]
        result = self._try_resolve(thunk_rva)
        self._cache[thunk_rva] = result
        return result

    def _try_resolve(self, thunk_rva: int) -> Optional[int]:
        code = self._read_bytes(thunk_rva, 256)
        if code is None:
            return None

        va = self._base + thunk_rva
        insns = list(self._md.disasm(code, va, count=MAX_THUNK_INSNS))
        if not insns:
            return None

        # Pattern 1: MOV RAX, imm64; JMP RAX
        r = self._pat_mov_reg_jmp(insns)
        if r:
            return r

        # Pattern 2: JMP [RIP+disp32] — indirect through pointer
        r = self._pat_jmp_rip_indirect(insns)
        if r:
            return r

        # Pattern 3: PUSH low32; MOV [RSP+4], high32; RET
        r = self._pat_push_mov_ret(insns)
        if r:
            return r

        # Pattern 4: MOV RAX, enc; MOV RCX, key; XOR RAX, RCX; JMP RAX
        r = self._pat_xor_decode(insns)
        if r:
            return r

        # Pattern 5: LEA RAX, [RIP+disp32]; JMP RAX
        r = self._pat_lea_jmp(insns)
        if r:
            return r

        # Pattern 6: PUSH RAX; MOV RAX, imm64; XCHG [RSP], RAX; RET
        r = self._pat_push_xchg_ret(insns)
        if r:
            return r

        # Pattern 7: SUB RSP, 8; MOV [RSP], imm32; MOV [RSP+4], imm32; RET
        r = self._pat_sub_rsp_store_ret(insns)
        if r:
            return r

        return None

    def _pat_mov_reg_jmp(self, insns: list[CsInsn]) -> Optional[int]:
        gprs = {X86_REG_RAX, X86_REG_RBX, X86_REG_RCX, X86_REG_RDX}
        for i in range(len(insns) - 1):
            ci = insns[i]
            ni = insns[i + 1]
            if (
                ci.mnemonic.startswith("mov")
                and len(ci.operands) == 2
                and ci.operands[0].reg in gprs
                and ci.operands[1].type == X86_OP_IMM
            ):
                target_reg = ci.operands[0].reg
                imm = ci.operands[1].imm & 0xFFFFFFFFFFFFFFFF
                if (
                    ni.mnemonic == "jmp"
                    and len(ni.operands) == 1
                    and ni.operands[0].reg == target_reg
                ):
                    return imm
        return None

    def _pat_jmp_rip_indirect(self, insns: list[CsInsn]) -> Optional[int]:
        for ci in insns[:4]:
            if ci.mnemonic == "jmp" and len(ci.operands) == 1:
                op = ci.operands[0]
                if (
                    op.type == X86_OP_MEM
                    and op.mem.base == X86_REG_RIP
                    and op.mem.index == 0
                ):
                    ptr_va = ci.address + ci.size + op.mem.disp
                    ptr_rva = ptr_va - self._base
                    val = self._read_qword(ptr_rva)
                    if val and val > 0x7FF000000000:
                        return val
        return None

    def _pat_push_mov_ret(self, insns: list[CsInsn]) -> Optional[int]:
        if len(insns) < 3:
            return None
        for i in range(len(insns) - 2):
            pi, mi, ri = insns[i], insns[i + 1], insns[i + 2]
            if pi.mnemonic != "push" or len(pi.operands) != 1:
                continue
            if pi.operands[0].type != X86_OP_IMM:
                continue
            low32 = pi.operands[0].imm & 0xFFFFFFFF
            if (
                mi.mnemonic == "mov"
                and len(mi.operands) == 2
                and mi.operands[0].type == X86_OP_MEM
                and mi.operands[0].mem.base == X86_REG_RSP
                and mi.operands[0].mem.disp == 4
                and mi.operands[1].type == X86_OP_IMM
            ):
                high32 = mi.operands[1].imm & 0xFFFFFFFF
                if ri.mnemonic == "ret":
                    return (high32 << 32) | low32
        return None

    def _pat_xor_decode(self, insns: list[CsInsn]) -> Optional[int]:
        regs_val: dict[int, int] = {}
        for i, ci in enumerate(insns):
            if (
                ci.mnemonic.startswith("mov")
                and len(ci.operands) == 2
                and ci.operands[1].type == X86_OP_IMM
            ):
                regs_val[ci.operands[0].reg] = ci.operands[1].imm & 0xFFFFFFFFFFFFFFFF

            if ci.mnemonic == "xor" and len(ci.operands) == 2:
                dst = ci.operands[0].reg
                src = ci.operands[1]
                if src.type == X86_OP_IMM:
                    if dst in regs_val:
                        # sign-extend 32-bit immediate
                        key = src.imm
                        if key < 0:
                            key = key & 0xFFFFFFFFFFFFFFFF
                        regs_val[dst] ^= key
                elif src.reg in regs_val and dst in regs_val:
                    regs_val[dst] ^= regs_val[src.reg]

            if ci.mnemonic == "jmp" and len(ci.operands) == 1:
                op = ci.operands[0]
                if op.reg in regs_val:
                    val = regs_val[op.reg]
                    if val > 0x7FF000000000:
                        return val
        return None

    def _pat_lea_jmp(self, insns: list[CsInsn]) -> Optional[int]:
        gprs = {X86_REG_RAX, X86_REG_RBX, X86_REG_RCX, X86_REG_RDX}
        for i in range(len(insns) - 1):
            ci = insns[i]
            ni = insns[i + 1]
            if (
                ci.mnemonic == "lea"
                and len(ci.operands) == 2
                and ci.operands[0].reg in gprs
                and ci.operands[1].type == X86_OP_MEM
                and ci.operands[1].mem.base == X86_REG_RIP
            ):
                target_va = ci.address + ci.size + ci.operands[1].mem.disp
                target_reg = ci.operands[0].reg
                if (
                    ni.mnemonic == "jmp"
                    and len(ni.operands) == 1
                    and ni.operands[0].reg == target_reg
                ):
                    return target_va
        return None

    def _pat_push_xchg_ret(self, insns: list[CsInsn]) -> Optional[int]:
        if len(insns) < 4:
            return None
        for i in range(len(insns) - 3):
            a, b, c, d = insns[i], insns[i + 1], insns[i + 2], insns[i + 3]
            if a.mnemonic != "push":
                continue
            if (
                b.mnemonic.startswith("mov")
                and len(b.operands) == 2
                and b.operands[1].type == X86_OP_IMM
            ):
                imm = b.operands[1].imm & 0xFFFFFFFFFFFFFFFF
                mov_reg = b.operands[0].reg
                if (
                    c.mnemonic == "xchg"
                    and len(c.operands) == 2
                    and c.operands[0].type == X86_OP_MEM
                    and c.operands[0].mem.base == X86_REG_RSP
                    and c.operands[1].reg == mov_reg
                    and d.mnemonic == "ret"
                ):
                    return imm
        return None

    def _pat_sub_rsp_store_ret(self, insns: list[CsInsn]) -> Optional[int]:
        if len(insns) < 4:
            return None
        for i in range(len(insns) - 3):
            a = insns[i]
            if (
                a.mnemonic == "sub"
                and len(a.operands) == 2
                and a.operands[0].reg == X86_REG_RSP
                and a.operands[1].type == X86_OP_IMM
                and a.operands[1].imm == 8
            ):
                b, c = insns[i + 1], insns[i + 2]
                lo = hi = None
                for m in (b, c):
                    if (
                        m.mnemonic == "mov"
                        and len(m.operands) == 2
                        and m.operands[0].type == X86_OP_MEM
                        and m.operands[0].mem.base == X86_REG_RSP
                        and m.operands[1].type == X86_OP_IMM
                    ):
                        disp = m.operands[0].mem.disp
                        val = m.operands[1].imm & 0xFFFFFFFF
                        if disp == 0:
                            lo = val
                        elif disp == 4:
                            hi = val
                if lo is not None and hi is not None:
                    for k in range(i + 3, min(i + 5, len(insns))):
                        if insns[k].mnemonic == "ret":
                            return (hi << 32) | lo
        return None


class CallSiteScanner:
    def __init__(self, pe: pefile.PE, vmp_rva: int, vmp_size: int, image_base: int):
        self._pe = pe
        self._vmp_lo = vmp_rva
        self._vmp_hi = vmp_rva + vmp_size
        self._base = image_base

    def _in_vmp(self, rva: int) -> bool:
        return self._vmp_lo <= rva < self._vmp_hi

    def scan(self) -> list[CallSite]:
        sites: list[CallSite] = []
        text_sec = None
        for sec in self._pe.sections:
            name = sec.Name.rstrip(b"\x00").decode("ascii", errors="replace")
            if name == ".text":
                text_sec = sec
                break
        if text_sec is None:
            for sec in self._pe.sections:
                if sec.Characteristics & 0x20000000:  # IMAGE_SCN_MEM_EXECUTE
                    text_sec = sec
                    break
        if text_sec is None:
            print("[!] no executable section found", file=sys.stderr)
            return sites

        data = self._pe.__data__
        sec_rva = text_sec.VirtualAddress
        sec_off = text_sec.PointerToRawData
        sec_size = min(text_sec.SizeOfRawData, text_sec.Misc_VirtualSize)

        for i in range(sec_size - 5):
            off = sec_off + i
            rva = sec_rva + i
            b0 = data[off]

            # E8 rel32 / E9 rel32
            if b0 in (CALL_REL32_OP, JMP_REL32_OP):
                rel32 = struct.unpack_from("<i", data, off + 1)[0]
                target_rva = rva + 5 + rel32
                if self._in_vmp(target_rva):
                    sites.append(
                        CallSite(
                            rva=rva,
                            size=5,
                            is_indirect=False,
                            target_rva=target_rva,
                            iat_slot_rva=None,
                        )
                    )

            # FF 15 disp32 / FF 25 disp32
            if off + 6 <= len(data) and b0 == 0xFF and data[off + 1] in (0x15, 0x25):
                disp32 = struct.unpack_from("<i", data, off + 2)[0]
                slot_rva = rva + 6 + disp32
                slot_off = None
                try:
                    slot_off = self._pe.get_offset_from_rva(slot_rva)
                except pefile.PEFormatError:
                    continue
                if slot_off and slot_off + 8 <= len(data):
                    ptr_val = struct.unpack_from("<Q", data, slot_off)[0]
                    ptr_rva = ptr_val - self._base
                    if self._in_vmp(ptr_rva):
                        sites.append(
                            CallSite(
                                rva=rva,
                                size=6,
                                is_indirect=True,
                                target_rva=ptr_rva,
                                iat_slot_rva=slot_rva,
                            )
                        )

        return sites


@dataclass
class ImportEntry:
    dll: str
    name: str
    ordinal: int
    hint: int = 0


@dataclass
class IATLayout:
    iat_rva: int
    ilt_rva: int
    names_rva: int
    descs_rva: int
    total_size: int
    slot_map: dict[str, dict[str, int]] = field(default_factory=dict)


class IATBuilder:
    def __init__(self, pe: pefile.PE, image_base: int):
        self._pe = pe
        self._base = image_base

    def build(
        self,
        imports: dict[str, list[ImportEntry]],
        base_rva: int,
    ) -> tuple[IATLayout, bytes]:
        dll_count = len(imports)
        total_funcs = sum(len(funcs) for funcs in imports.values())

        descs_size = (dll_count + 1) * IMPORT_DESC_SIZE  # +1 null terminator
        ilt_size = sum((len(funcs) + 1) * 8 for funcs in imports.values())
        iat_size = ilt_size

        names_size = 0
        for dll_name, funcs in imports.items():
            names_size += len(dll_name.encode()) + 1
            if names_size % 2:
                names_size += 1
            for entry in funcs:
                if entry.name and not entry.name.startswith("__ordinal_"):
                    # HINT(2) + name + null
                    entry_size = 2 + len(entry.name.encode()) + 1
                    if entry_size % HINT_NAME_ALIGN:
                        entry_size += 1
                    names_size += entry_size

        descs_rva = base_rva
        ilt_rva = descs_rva + descs_size
        iat_rva = ilt_rva + ilt_size
        names_rva = iat_rva + iat_size
        total_size = descs_size + ilt_size + iat_size + names_size

        buf = bytearray(total_size)
        slot_map: dict[str, dict[str, int]] = {}

        # write names block
        names_cursor = 0
        dll_name_offsets: dict[str, int] = {}
        func_hint_offsets: dict[str, dict[str, int]] = {}

        for dll_name, funcs in imports.items():
            dll_name_offsets[dll_name] = names_rva + names_cursor
            encoded = dll_name.encode() + b"\x00"
            buf[names_rva - base_rva + names_cursor : names_rva - base_rva + names_cursor + len(encoded)] = encoded
            names_cursor += len(encoded)
            if names_cursor % 2:
                names_cursor += 1

            func_hint_offsets[dll_name] = {}
            for entry in funcs:
                if entry.name and not entry.name.startswith("__ordinal_"):
                    func_hint_offsets[dll_name][entry.name] = names_rva + names_cursor
                    hint_bytes = struct.pack("<H", entry.hint)
                    name_bytes = entry.name.encode() + b"\x00"
                    entry_bytes = hint_bytes + name_bytes
                    if len(entry_bytes) % HINT_NAME_ALIGN:
                        entry_bytes += b"\x00"
                    start = names_rva - base_rva + names_cursor
                    buf[start : start + len(entry_bytes)] = entry_bytes
                    names_cursor += len(entry_bytes)

        # write ILT, IAT, and descriptors
        ilt_cursor = 0
        iat_cursor = 0
        desc_cursor = 0

        for dll_name, funcs in imports.items():
            slot_map[dll_name] = {}

            # IMAGE_IMPORT_DESCRIPTOR
            struct.pack_into(
                "<IIIII",
                buf,
                desc_cursor,
                ilt_rva + ilt_cursor,               # OriginalFirstThunk (ILT)
                0,                                   # TimeDateStamp
                0xFFFFFFFF,                          # ForwarderChain
                dll_name_offsets[dll_name],           # Name RVA
                iat_rva + iat_cursor,                # FirstThunk (IAT)
            )
            desc_cursor += IMPORT_DESC_SIZE

            for entry in funcs:
                if entry.name and not entry.name.startswith("__ordinal_"):
                    thunk_val = func_hint_offsets[dll_name][entry.name]
                else:
                    thunk_val = 0x8000000000000000 | (entry.ordinal & 0xFFFF)

                # ILT entry
                ilt_off = (ilt_rva - base_rva) + ilt_cursor
                struct.pack_into("<Q", buf, ilt_off, thunk_val)

                # IAT entry (same value, runtime loader patches this)
                iat_off = (iat_rva - base_rva) + iat_cursor
                struct.pack_into("<Q", buf, iat_off, thunk_val)

                slot_map[dll_name][entry.name or f"ord_{entry.ordinal}"] = iat_rva + iat_cursor
                ilt_cursor += 8
                iat_cursor += 8

            # null terminator for this DLL's ILT/IAT
            ilt_cursor += 8
            iat_cursor += 8

        # null terminator descriptor
        # (already zeroed)

        layout = IATLayout(
            iat_rva=iat_rva,
            ilt_rva=ilt_rva,
            names_rva=names_rva,
            descs_rva=descs_rva,
            total_size=total_size,
            slot_map=slot_map,
        )
        return layout, bytes(buf)


class PEPatcher:
    def __init__(self, pe: pefile.PE, image_base: int):
        self._pe = pe
        self._base = image_base
        self._data = bytearray(pe.__data__)

    def _rva_to_offset(self, rva: int) -> Optional[int]:
        try:
            return self._pe.get_offset_from_rva(rva)
        except pefile.PEFormatError:
            return None

    def write_block(self, rva: int, data: bytes):
        off = self._rva_to_offset(rva)
        if off is None:
            raise ValueError(f"cannot map RVA {rva:#x} to file offset")
        self._data[off : off + len(data)] = data

    def patch_indirect_site(self, site: CallSite, new_iat_slot_rva: int):
        # FF 15/25 disp32 — just fix the disp32 to point at new IAT slot
        off = self._rva_to_offset(site.rva)
        if off is None:
            return
        new_disp = new_iat_slot_rva - (site.rva + 6)
        struct.pack_into("<i", self._data, off + 2, new_disp)

    def patch_direct_site(self, site: CallSite, trampoline_rva: int):
        # E8/E9 rel32 — retarget to trampoline
        off = self._rva_to_offset(site.rva)
        if off is None:
            return
        new_rel = trampoline_rva - (site.rva + 5)
        struct.pack_into("<i", self._data, off + 1, new_rel)

    def build_trampoline(self, tramp_rva: int, iat_slot_rva: int) -> bytes:
        # FF 25 disp32(rip-relative) -> JMP [IAT_slot]
        disp = iat_slot_rva - (tramp_rva + 6)
        return b"\xFF\x25" + struct.pack("<i", disp) + b"\xCC" * 8

    def update_import_directory(self, desc_rva: int, total_size: int):
        dd_off = self._pe.OPTIONAL_HEADER.DATA_DIRECTORY[IMAGE_DIRECTORY_ENTRY_IMPORT]
        dd_off.VirtualAddress = desc_rva
        dd_off.Size = total_size

        # re-encode the optional header
        header_off = self._pe.OPTIONAL_HEADER.get_file_offset()
        dd_entry_off = header_off + 0x78 + IMAGE_DIRECTORY_ENTRY_IMPORT * 8  # x64 offset
        struct.pack_into("<II", self._data, dd_entry_off, desc_rva, total_size)

    def zero_range(self, rva: int, size: int):
        off = self._rva_to_offset(rva)
        if off:
            self._data[off : off + size] = b"\x00" * size

    def get_data(self) -> bytes:
        return bytes(self._data)


def find_vmp_section(pe: pefile.PE) -> Optional[pefile.SectionStructure]:
    for sec in pe.sections:
        name = sec.Name.rstrip(b"\x00").decode("ascii", errors="replace")
        if name == ".vmp0":
            return sec
    for sec in pe.sections:
        name = sec.Name.rstrip(b"\x00").decode("ascii", errors="replace")
        if name.startswith(".vmp"):
            return sec
    return None


def main():
    ap = argparse.ArgumentParser(description="VMP 3.8 x64 IAT rebuilder")
    ap.add_argument("dump", help="dumped PE path")
    ap.add_argument("modules", help="module map JSON (gen_modmap.py output)")
    ap.add_argument("-o", "--output", required=True, help="rebuilt PE output path")
    ap.add_argument("--imagebase", type=lambda x: int(x, 16), default=None,
                     help="override image base (hex)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    pe = pefile.PE(args.dump, fast_load=False)
    if pe.FILE_HEADER.Machine != 0x8664:
        print("[!] not AMD64 PE", file=sys.stderr)
        sys.exit(1)

    image_base = args.imagebase or pe.OPTIONAL_HEADER.ImageBase
    modmap = ModuleMap(args.modules)

    vmp_sec = find_vmp_section(pe)
    if vmp_sec is None:
        print("[!] .vmp0 section not found", file=sys.stderr)
        sys.exit(1)

    vmp_rva = vmp_sec.VirtualAddress
    vmp_size = vmp_sec.Misc_VirtualSize
    vmp_name = vmp_sec.Name.rstrip(b"\x00").decode("ascii", errors="replace")
    print(f"[*] {vmp_name} @ RVA {vmp_rva:#x}, size {vmp_size:#x}")

    resolver = ThunkResolver(pe, vmp_rva, vmp_size, image_base)
    scanner = CallSiteScanner(pe, vmp_rva, vmp_size, image_base)

    print("[*] scanning call sites...")
    sites = scanner.scan()
    print(f"[*] {len(sites)} call/jmp into VMP section")

    resolved_sites: list[tuple[CallSite, ResolvedImport]] = []
    unresolved: list[CallSite] = []
    thunk_targets: dict[int, Optional[int]] = {}

    for site in sites:
        if site.target_rva not in thunk_targets:
            addr = resolver.resolve(site.target_rva)
            thunk_targets[site.target_rva] = addr

        api_addr = thunk_targets[site.target_rva]
        if api_addr is None:
            unresolved.append(site)
            continue

        imp = modmap.resolve(api_addr)
        if imp is None:
            unresolved.append(site)
            if args.verbose:
                print(f"  [?] thunk {site.target_rva:#x} -> {api_addr:#x} not in module map")
            continue

        resolved_sites.append((site, imp))
        if args.verbose:
            print(f"  [+] {site.rva:#x} -> {imp.dll}!{imp.name}")

    print(f"[*] resolved: {len(resolved_sites)}, unresolved: {len(unresolved)}")

    if not resolved_sites:
        print("[!] nothing resolved, check module map", file=sys.stderr)
        sys.exit(1)

    # group by DLL
    dll_imports: dict[str, dict[str, ImportEntry]] = {}
    for site, imp in resolved_sites:
        dll = imp.dll.lower()
        if dll not in dll_imports:
            dll_imports[dll] = {}
        key = imp.name
        if key not in dll_imports[dll]:
            dll_imports[dll][key] = ImportEntry(
                dll=imp.dll, name=imp.name, ordinal=imp.ordinal
            )

    ordered_imports: dict[str, list[ImportEntry]] = {
        dll: list(entries.values()) for dll, entries in sorted(dll_imports.items())
    }

    # place new import directory inside .vmp0 section (reuse its space)
    builder = IATBuilder(pe, image_base)
    layout, iat_data = builder.build(ordered_imports, vmp_rva)

    if layout.total_size > vmp_size:
        print(f"[!] new IAT ({layout.total_size:#x}) exceeds .vmp0 ({vmp_size:#x})", file=sys.stderr)
        sys.exit(1)

    # allocate trampolines after the IAT data
    tramp_base_rva = vmp_rva + layout.total_size
    tramp_base_rva = (tramp_base_rva + 15) & ~15  # align 16

    # build unique trampoline for each (dll, name) used by direct call sites
    trampoline_map: dict[tuple[str, str], int] = {}
    tramp_cursor = tramp_base_rva

    patcher = PEPatcher(pe, image_base)

    # zero out .vmp0 first
    patcher.zero_range(vmp_rva, vmp_size)

    # write the new import directory
    patcher.write_block(vmp_rva, iat_data)

    # patch all call sites
    for site, imp in resolved_sites:
        dll_key = imp.dll.lower()
        name_key = imp.name
        iat_slot_rva = layout.slot_map[dll_key][name_key]

        if site.is_indirect:
            patcher.patch_indirect_site(site, iat_slot_rva)
        else:
            tkey = (dll_key, name_key)
            if tkey not in trampoline_map:
                if tramp_cursor + TRAMPOLINE_STUB_SIZE > vmp_rva + vmp_size:
                    print("[!] not enough space for trampolines", file=sys.stderr)
                    sys.exit(1)
                tramp_code = patcher.build_trampoline(tramp_cursor, iat_slot_rva)
                patcher.write_block(tramp_cursor, tramp_code)
                trampoline_map[tkey] = tramp_cursor
                tramp_cursor += TRAMPOLINE_STUB_SIZE

            patcher.patch_direct_site(site, trampoline_map[tkey])

    patcher.update_import_directory(layout.descs_rva, layout.total_size)

    out = patcher.get_data()
    Path(args.output).write_bytes(out)
    print(f"[*] wrote {args.output} ({len(out)} bytes)")
    print(f"[*] new import dir @ RVA {layout.descs_rva:#x}")
    print(f"[*] IAT @ RVA {layout.iat_rva:#x}")
    print(f"[*] {len(trampoline_map)} trampolines @ RVA {tramp_base_rva:#x}")
    print(f"[*] {sum(len(v) for v in ordered_imports.values())} APIs across {len(ordered_imports)} DLLs")


if __name__ == "__main__":
    main()
