"""Forensic instrumentation for silent crash diagnosis.

Wraps the process with four layers so that future deaths leave evidence:

  1. faulthandler — catches segfaults / SIGSEGV / SIGABRT / SIGFPE and dumps
     Python tracebacks of every thread to the forensic log. Also dumps
     periodic snapshots on a configurable interval so we see what the
     interpreter was running just before death (useful even for SIGKILL,
     since the prior snapshot survives).

  2. tracemalloc — tracks heap allocations from process start. On any
     uncaught exception OR at normal exit, the top-30 allocation sites
     (current + peak) are written to the forensic log.

  3. memory watchdog — a daemon thread polls RSS every 5s and writes it
     to the log. SIGKILL (Linux OOM-killer) is uncatchable, so the
     watchdog's last line tells us how much memory was held the instant
     before the kernel killed the process.

  4. signal traps — SIGTERM / SIGINT print final state before exiting.

USAGE:
    from core.forensic_trap import install
    install()    # call once, at the very top of the entry point

The trap can be disabled by setting ESG_FORENSIC_TRAP=0.
"""
from __future__ import annotations

import atexit
import faulthandler
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

_INSTALLED = False
_LOGFILE: Optional[TextIO] = None
_LOGPATH: Optional[Path] = None
_WATCHDOG_RUNNING = threading.Event()
_DUMP_EVERY_SECONDS = 60     # periodic stack snapshot
_WATCHDOG_EVERY_SECONDS = 5  # RSS poll


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def _read_rss_bytes() -> Optional[int]:
    """Process RSS in bytes. Linux/WSL → /proc; Windows → GetProcessMemoryInfo
    via ctypes (no psutil dependency)."""
    # Linux/WSL fast path
    try:
        with open("/proc/self/status", "r") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except Exception:
        pass
    # Windows fallback — Working Set Size is the closest analogue to RSS
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = _PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.WinDLL("psapi.dll")
            kernel32 = ctypes.WinDLL("kernel32.dll")
            # Explicit signatures — required on 64-bit Windows or the call
            # silently misbehaves (HANDLE-truncation, BOOL-default-int).
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return int(pmc.WorkingSetSize)
        except Exception:
            pass
    return None


def _read_meminfo_available_bytes() -> Optional[int]:
    # Linux/WSL fast path
    try:
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except Exception:
        pass
    # Windows fallback — GlobalMemoryStatusEx via ctypes
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = _MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            kernel32 = ctypes.WinDLL("kernel32.dll")
            kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
            kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
            if kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                return int(mem.ullAvailPhys)
        except Exception:
            pass
    return None


def _fmt_mb(n: Optional[int]) -> str:
    if n is None:
        return "?"
    return f"{n / (1024 * 1024):.1f} MB"


def _watchdog_loop():
    last_rss = -1
    while _WATCHDOG_RUNNING.is_set():
        rss = _read_rss_bytes()
        avail = _read_meminfo_available_bytes()
        if rss is not None and abs(rss - last_rss) > 50 * 1024 * 1024:
            # log only when RSS changes by >50MB to keep the log tight
            _write(f"[watchdog {_now()}] rss={_fmt_mb(rss)} avail={_fmt_mb(avail)}")
            last_rss = rss
        time.sleep(_WATCHDOG_EVERY_SECONDS)


def _write(msg: str) -> None:
    if _LOGFILE is None:
        return
    try:
        _LOGFILE.write(msg + "\n")
        _LOGFILE.flush()
    except Exception:
        pass


def _dump_tracemalloc(label: str) -> None:
    try:
        import tracemalloc
        if not tracemalloc.is_tracing():
            return
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")[:30]
        current, peak = tracemalloc.get_traced_memory()
        _write("")
        _write(f"───── tracemalloc snapshot @ {label} ─────")
        _write(f"  current={_fmt_mb(current)}  peak={_fmt_mb(peak)}")
        _write(f"  top-30 allocation sites:")
        for i, stat in enumerate(stats, 1):
            _write(f"    {i:2d}. {_fmt_mb(stat.size)}  {stat.traceback}")
        _write("─" * 60)
    except Exception as e:
        _write(f"[tracemalloc dump failed: {e}]")


def _on_exit() -> None:
    rss = _read_rss_bytes()
    _write(f"[exit {_now()}] rss={_fmt_mb(rss)}")
    _dump_tracemalloc("exit")
    _WATCHDOG_RUNNING.clear()


def _on_signal(signum, frame):
    name = signal.Signals(signum).name
    _write("")
    _write(f"!!!!! caught {name} @ {_now()} — dumping state !!!!!")
    _write(f"rss={_fmt_mb(_read_rss_bytes())} avail={_fmt_mb(_read_meminfo_available_bytes())}")
    _write("\n--- current thread tracebacks ---")
    for tid, frm in sys._current_frames().items():
        _write(f"\nThread {tid}:")
        _write("".join(traceback.format_stack(frm)))
    _dump_tracemalloc(name)
    if _LOGFILE is not None:
        _LOGFILE.flush()
    # restore default handler and re-raise so the OS sees the signal naturally
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def install() -> Optional[Path]:
    """Install the forensic trap. Returns the path to the log file (or None
    if disabled). Idempotent — calling twice is a no-op."""
    global _INSTALLED, _LOGFILE, _LOGPATH

    if _INSTALLED:
        return _LOGPATH
    if os.getenv("ESG_FORENSIC_TRAP", "1").lower() in {"0", "false", "no"}:
        return None

    log_dir = Path(os.getenv("ESG_FORENSIC_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    _LOGPATH = log_dir / f"forensic_{os.getpid()}_{stamp}.log"
    _LOGFILE = open(_LOGPATH, "a", encoding="utf-8", buffering=1)

    _write(f"[install {_now()}] pid={os.getpid()} log={_LOGPATH}")
    _write(f"  python={sys.version.split()[0]}  argv={sys.argv}")
    _write(f"  start rss={_fmt_mb(_read_rss_bytes())} avail={_fmt_mb(_read_meminfo_available_bytes())}")

    # 1. faulthandler — fatal-signal logging only.
    #
    # We deliberately DO NOT call faulthandler.dump_traceback_later() here.
    # On Windows, the periodic traceback dump runs in a background OS
    # thread that interrupts the main thread via SetEvent + signal-like
    # mechanism; if the interrupt lands while a thread is mid-DLL-load
    # (e.g. torch, chardet, transformers during their C-level init),
    # thread state corrupts and Python crashes with a 0xC0000005 access
    # violation. The crashes look like bugs in the loaded library, but
    # the actual trigger is the dump. Set ESG_FORENSIC_DUMP=1 to re-enable
    # the periodic dump for hang debugging.
    try:
        faulthandler.enable(file=_LOGFILE, all_threads=True)
        if os.getenv("ESG_FORENSIC_DUMP", "").lower() in {"1", "true", "yes"}:
            faulthandler.dump_traceback_later(
                _DUMP_EVERY_SECONDS, repeat=True, file=_LOGFILE
            )
            _write("[faulthandler] periodic dump ENABLED (ESG_FORENSIC_DUMP=1)")
        else:
            _write("[faulthandler] passive crash-logging only; periodic dump disabled")
    except Exception as e:
        _write(f"[faulthandler setup failed: {e}]")

    # 2. tracemalloc
    try:
        import tracemalloc
        tracemalloc.start(25)  # 25 frames per traceback
    except Exception as e:
        _write(f"[tracemalloc start failed: {e}]")

    # 3. watchdog
    _WATCHDOG_RUNNING.set()
    threading.Thread(target=_watchdog_loop, name="forensic-watchdog", daemon=True).start()

    # 4. signal handlers (SIGKILL cannot be caught — that's why the
    #    watchdog matters)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_signal)
        except Exception:
            pass

    atexit.register(_on_exit)

    _INSTALLED = True
    return _LOGPATH


def report_exception(exc: BaseException) -> None:
    """Call from a top-level except: dumps the traceback + tracemalloc state."""
    if not _INSTALLED:
        return
    _write("")
    _write(f"!!!!! uncaught exception @ {_now()} !!!!!")
    _write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    _dump_tracemalloc("exception")
