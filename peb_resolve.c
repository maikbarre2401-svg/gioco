/*
 * peb_resolve.c — dynamic API resolution via PEB walk
 * No IAT entries for target functions, no GetProcAddress.
 * Walks InMemoryOrderModuleList to find DLL bases, then
 * walks each module's export table to resolve by name.
 *
 * Target : Windows 11 23H2 x64, MSVC 19.4x
 * Build  : cl /GS- /O2 peb_resolve.c /link /ENTRY:main /SUBSYSTEM:CONSOLE kernel32.lib
 */

#include <windows.h>

typedef LONG NTSTATUS;
#define NT_SUCCESS(s) ((s) >= 0)

/* ---------- function pointer typedefs (match SDK prototypes) ---------- */

typedef LPVOID (WINAPI *fn_VirtualAlloc)(
    LPVOID lpAddress,
    SIZE_T dwSize,
    DWORD  flAllocationType,
    DWORD  flProtect
);

typedef BOOL (WINAPI *fn_VirtualProtect)(
    LPVOID lpAddress,
    SIZE_T dwSize,
    DWORD  flNewProtect,
    PDWORD lpflOldProtect
);

typedef NTSTATUS (NTAPI *fn_NtCreateThreadEx)(
    PHANDLE     hThread,
    ACCESS_MASK desiredAccess,
    PVOID       objectAttributes,
    HANDLE      processHandle,
    PVOID       startRoutine,
    PVOID       argument,
    ULONG       createFlags,
    SIZE_T      zeroBits,
    SIZE_T      stackSize,
    SIZE_T      maximumStackSize,
    PVOID       attributeList
);

/* ---------- no-CRT string helpers ---------- */

static __forceinline int w_eq_ci(const wchar_t *a, const wchar_t *b)
{
    for (;; a++, b++) {
        wchar_t ca = *a, cb = *b;
        if (ca >= L'A' && ca <= L'Z') ca += 0x20;
        if (cb >= L'A' && cb <= L'Z') cb += 0x20;
        if (ca != cb)   return 0;
        if (!*a)        return 1;
    }
}

static __forceinline int a_eq(const char *a, const char *b)
{
    for (;; a++, b++) {
        if (*a != *b)   return 0;
        if (!*a)        return 1;
    }
}

/* ---------- PEB walk: find DLL base by name ---------- */
/*
 * x64 LDR_DATA_TABLE_ENTRY layout (relevant fields):
 *   +0x000  InLoadOrderLinks           LIST_ENTRY
 *   +0x010  InMemoryOrderLinks         LIST_ENTRY
 *   +0x020  InInitializationOrderLinks LIST_ENTRY
 *   +0x030  DllBase                    PVOID
 *   +0x038  EntryPoint                 PVOID
 *   +0x040  SizeOfImage                ULONG
 *   +0x048  FullDllName                UNICODE_STRING
 *   +0x058  BaseDllName                UNICODE_STRING
 *
 * UNICODE_STRING on x64: Length(2) + MaxLen(2) + pad(4) + Buffer(8) = 16 bytes
 *
 * When walking InMemoryOrderModuleList, Flink points to the
 * InMemoryOrderLinks field (+0x10). Offsets from that pointer:
 *   DllBase         = curr + 0x20   (0x30 - 0x10)
 *   BaseDllName.Len = curr + 0x48   (0x58 - 0x10)
 *   BaseDllName.Buf = curr + 0x50   (0x58 - 0x10 + 0x08)
 */

static PVOID find_dll(const wchar_t *name)
{
    BYTE *peb = (BYTE *)__readgsqword(0x60);
    BYTE *ldr = *(BYTE **)(peb + 0x18);

    LIST_ENTRY *head = (LIST_ENTRY *)(ldr + 0x20);
    LIST_ENTRY *curr = head->Flink;

    while (curr != head) {
        wchar_t *buf = *(wchar_t **)((BYTE *)curr + 0x50);
        if (buf && w_eq_ci(buf, name))
            return *(PVOID *)((BYTE *)curr + 0x20);
        curr = curr->Flink;
    }
    return NULL;
}

/* ---------- export table walk ---------- */
/*
 * PE32+ export resolution via raw offsets:
 *   DOS.e_lfanew                          @ base + 0x3C
 *   NT.OptionalHeader.DataDirectory[0]    @ nt   + 0x88
 *   EXPORT_DIR.NumberOfNames              @ exp  + 0x18
 *   EXPORT_DIR.AddressOfFunctions         @ exp  + 0x1C
 *   EXPORT_DIR.AddressOfNames             @ exp  + 0x20
 *   EXPORT_DIR.AddressOfNameOrdinals      @ exp  + 0x24
 */

static PVOID find_export(PVOID base, const char *func_name)
{
    BYTE *b  = (BYTE *)base;
    BYTE *nt = b + *(DWORD *)(b + 0x3C);

    DWORD exp_rva = *(DWORD *)(nt + 0x88);
    if (!exp_rva) return NULL;

    BYTE  *exp    = b + exp_rva;
    DWORD  exp_sz = *(DWORD *)(nt + 0x8C);
    DWORD  nnames = *(DWORD *)(exp + 0x18);
    DWORD *funcs  = (DWORD *)(b + *(DWORD *)(exp + 0x1C));
    DWORD *names  = (DWORD *)(b + *(DWORD *)(exp + 0x20));
    WORD  *ords   = (WORD  *)(b + *(DWORD *)(exp + 0x24));

    for (DWORD i = 0; i < nnames; i++) {
        if (a_eq((const char *)(b + names[i]), func_name)) {
            DWORD func_rva = funcs[ords[i]];
            /* forwarder check: RVA inside export dir → forwarded, skip */
            if (func_rva >= exp_rva && func_rva < exp_rva + exp_sz)
                return NULL;
            return b + func_rva;
        }
    }
    return NULL;
}

/* ---------- smoke test ---------- */

int main(void)
{
    PVOID k32 = find_dll(L"kernel32.dll");
    PVOID ntd = find_dll(L"ntdll.dll");
    if (!k32 || !ntd) return 1;

    fn_VirtualAlloc     pVA  = (fn_VirtualAlloc)    find_export(k32, "VirtualAlloc");
    fn_VirtualProtect   pVP  = (fn_VirtualProtect)  find_export(k32, "VirtualProtect");
    fn_NtCreateThreadEx pNTE = (fn_NtCreateThreadEx)find_export(ntd, "NtCreateThreadEx");
    if (!pVA || !pVP || !pNTE) return 2;

    /* alloc RW page, write RET, flip to RX, spawn thread via NtCreateThreadEx */
    BYTE *mem = (BYTE *)pVA(NULL, 0x1000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!mem) return 3;

    mem[0] = 0xC3;

    DWORD old;
    pVP(mem, 0x1000, PAGE_EXECUTE_READ, &old);

    HANDLE ht = NULL;
    NTSTATUS st = pNTE(
        &ht,
        THREAD_ALL_ACCESS,
        NULL,
        (HANDLE)(LONG_PTR)-1,   /* NtCurrentProcess(), no IAT hit */
        mem,
        NULL,
        0, 0, 0, 0, NULL
    );

    if (NT_SUCCESS(st) && ht) {
        WaitForSingleObject(ht, INFINITE);
        CloseHandle(ht);
    }

    return (int)st;
}
