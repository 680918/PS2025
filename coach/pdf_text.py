"""Short-lived PDF text worker. No AI, network, executable PDF content or OCR."""

import io
import json
import logging
import sys


def _memory_limit():
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
        return None
    import ctypes
    from ctypes import wintypes

    class IO(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read",
                "write",
                "other",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("min_ws", ctypes.c_size_t),
            ("max_ws", ctypes.c_size_t),
            ("processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", IO),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = 0x100
    limits.process_memory = 768 * 1024**2
    if (
        not handle
        or not kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        or not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess())
    ):
        raise RuntimeError("worker limits unavailable")
    return handle  # Keep the handle alive until process exit.


def main():
    from pypdf import PdfReader, filters

    logging.disable(logging.CRITICAL)
    memory_handle = _memory_limit()
    for name in (
        "ZLIB_MAX_OUTPUT_LENGTH",
        "LZW_MAX_OUTPUT_LENGTH",
        "RUN_LENGTH_MAX_OUTPUT_LENGTH",
        "JBIG2_MAX_OUTPUT_LENGTH",
    ):
        setattr(filters, name, 4 * 1024**2)
    raw = sys.stdin.buffer.read(10 * 1024**2 + 1)
    if len(raw) > 10 * 1024**2:
        raise ValueError("size")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        return {"error": "encrypted"}
    if not 1 <= len(reader.pages) <= 500:
        return {"error": "pages"}
    pages, length = [], 0
    for index, page in enumerate(reader.pages):
        stream = page.get_contents()
        if stream and len(stream.get_data()) > 2 * 1024**2:
            return {"error": "complex"}
        text = (page.extract_text() or "").strip()
        length += len(text)
        if len(text) > 40000 or length > 500000:
            return {"error": "text_size"}
        if text:
            pages.append({"page": index + 1, "text": text})
    if not pages:
        return {"error": "scan"}
    return {
        "pages": pages,
        "page_count": len(reader.pages),
        "limited": memory_handle is not None or sys.platform != "win32",
    }


if __name__ == "__main__":
    try:
        result = main()
    except Exception:
        result = {"error": "invalid"}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
