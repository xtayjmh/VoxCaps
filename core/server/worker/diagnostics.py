"""Worker 启动失败时生成可独立带回的诊断报告。"""

from __future__ import annotations

import ctypes
import os
import platform
import struct
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from config_server import BASE_DIR, ServerConfig
from ..engines.llama_runtime import REQUIRED_RUNTIME_FILES, llama_runtime_dir


REPORT_PATH = Path(BASE_DIR) / 'logs' / 'worker_crash_latest.log'


def _safe_section(title: str, callback) -> list[str]:
    try:
        value = callback()
        if isinstance(value, (list, tuple)):
            lines = [str(item) for item in value]
        else:
            lines = str(value).splitlines() or ['<empty>']
    except BaseException as exc:
        lines = [f'<diagnostic failed: {type(exc).__name__}: {exc}>']
    return [f'[{title}]', *lines, '']


def _runtime_diagnostics() -> list[str]:
    runtime_dir = llama_runtime_dir()
    lines = [f'runtime_dir={runtime_dir}']
    for name in REQUIRED_RUNTIME_FILES:
        path = runtime_dir / name
        size = path.stat().st_size if path.is_file() else 0
        load_result = 'not tested'
        if os.name == 'nt' and path.is_file():
            try:
                ctypes.WinDLL(str(path))
                load_result = 'OK'
            except OSError as exc:
                load_result = f'FAILED: {exc}'
        lines.append(f'{name}: exists={path.is_file()}, size={size}, load={load_result}')
    return lines


def _onnx_diagnostics() -> list[str]:
    import onnxruntime

    return [
        f'version={onnxruntime.__version__}',
        f'available_providers={onnxruntime.get_available_providers()}',
    ]


def _gpu_diagnostics() -> str:
    command = [
        'powershell.exe',
        '-NoProfile',
        '-Command',
        'Get-CimInstance Win32_VideoController | '
        'Select-Object Name,DriverVersion,AdapterRAM | Format-List',
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=10,
        check=False,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    return completed.stdout.strip() or completed.stderr.strip() or '<no GPU information>'


def write_worker_crash_report(exc: BaseException, traceback_text: str) -> str:
    """尽力写出诊断报告，同时不掩盖原始 Worker 异常。"""
    sections = [
        'VoxCaps Worker startup crash report',
        f'time={datetime.now().isoformat(timespec="seconds")}',
        f'exception={type(exc).__name__}: {exc}',
        '',
        '[process]',
        f'python={sys.version}',
        f'executable={sys.executable}',
        f'frozen={getattr(sys, "frozen", False)}',
        f'architecture={struct.calcsize("P") * 8}-bit',
        f'platform={platform.platform()}',
        f'cwd={Path.cwd()}',
        f'base_dir={BASE_DIR}',
        f'model_type={ServerConfig.model_type}',
        '',
    ]
    sections.extend(_safe_section('llama.cpp runtime', _runtime_diagnostics))
    sections.extend(_safe_section('ONNX Runtime', _onnx_diagnostics))
    sections.extend(_safe_section('display adapters', _gpu_diagnostics))
    sections.extend([
        '[relevant environment]',
        f'PATH={os.environ.get("PATH", "")}',
        f'VK_ICD_FILENAMES={os.environ.get("VK_ICD_FILENAMES", "")}',
        f'GGML_VK_DISABLE_COOPMAT={os.environ.get("GGML_VK_DISABLE_COOPMAT", "")}',
        f'GGML_VK_DISABLE_F16={os.environ.get("GGML_VK_DISABLE_F16", "")}',
        '',
        '[python traceback]',
        traceback_text.rstrip(),
        '',
    ])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text('\n'.join(sections), encoding='utf-8')
    return str(REPORT_PATH)
