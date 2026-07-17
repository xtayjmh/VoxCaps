"""Shared llama.cpp native runtime location for every GGUF engine."""

from __future__ import annotations

from pathlib import Path


REQUIRED_RUNTIME_FILES = (
    'ggml.dll',
    'ggml-base.dll',
    'ggml-vulkan.dll',
    'llama.dll',
)


def llama_runtime_dir() -> Path:
    """Return the single native runtime directory shared by all engines."""
    return Path(__file__).resolve().parent / 'llama' / 'bin'


def require_llama_runtime() -> Path:
    """Fail with a precise message when a packaged runtime is incomplete."""
    runtime_dir = llama_runtime_dir()
    missing = [name for name in REQUIRED_RUNTIME_FILES if not (runtime_dir / name).is_file()]
    if missing:
        missing_text = ', '.join(missing)
        raise FileNotFoundError(
            f'llama.cpp 运行库不完整：{runtime_dir}；缺少：{missing_text}'
        )
    return runtime_dir
