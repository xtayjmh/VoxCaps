"""检查完整包与纯客户端 ZIP 的结构和共享行为文件一致性。"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

from PIL import Image

try:
    from scripts.llama_runtime_manifest import (
        LLAMA_RUNTIME_MARKER,
        LLAMA_RUNTIME_RELATIVE_DIR,
        REQUIRED_LLAMA_DLLS,
    )
except ModuleNotFoundError:
    from llama_runtime_manifest import (
        LLAMA_RUNTIME_MARKER,
        LLAMA_RUNTIME_RELATIVE_DIR,
        REQUIRED_LLAMA_DLLS,
    )


REQUIRED_ICON_SIZES = {
    (16, 16), (24, 24), (32, 32), (48, 48),
    (64, 64), (128, 128), (256, 256),
}
RELEASE_VERSION = '3.0.1'
SHARED_FILES = (
    'config_client.py',
    'assets/icon.ico',
    'core/client/audio/session.py',
    'core/client/island/view.py',
    'core/ui/window_icon.py',
)
GGUF_RUNTIME_FILES = tuple(
    (LLAMA_RUNTIME_RELATIVE_DIR / name).as_posix()
    for name in (*REQUIRED_LLAMA_DLLS, LLAMA_RUNTIME_MARKER)
)
SERVER_RUNTIME_FILES = (
    'internal/soundfile.pyc',
    'internal/_soundfile.pyc',
    'internal/_soundfile_data/libsndfile_x64.dll',
)


def _newest(paths) -> Path:
    candidates = list(paths)
    if not candidates:
        raise FileNotFoundError('未找到待验证的 Windows ZIP')
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _member(archive: zipfile.ZipFile, root: str, relative: str) -> bytes:
    name = f'{root}/{relative}'.replace('\\', '/')
    try:
        return archive.read(name)
    except KeyError as exc:
        raise RuntimeError(f'ZIP 缺少文件：{name}') from exc


def _verify_runtime_version(data: bytes, relative: str) -> None:
    text = data.decode('utf-8-sig')
    expected = f"__version__ = '{RELEASE_VERSION}'"
    if expected not in text:
        raise RuntimeError(f'ZIP 内运行时版本不是 {RELEASE_VERSION}：{relative}')


def verify_full_package_root(package_root: Path) -> Path:
    package_root = package_root.resolve()
    for relative in (*GGUF_RUNTIME_FILES, *SERVER_RUNTIME_FILES):
        runtime_file = package_root / relative
        if not runtime_file.is_file():
            raise RuntimeError(f'完整包缺少 Server 运行库：{runtime_file}')
    print(f'[VoxCaps] 完整包 Server 运行库检查通过：{package_root}')
    return package_root


def verify_packages(release_dir: Path) -> tuple[Path, Path]:
    full_zip = _newest(
        path for path in release_dir.glob('VoxCaps-*.zip')
        if not path.name.startswith('VoxCaps-Client-')
    )
    client_zip = _newest(release_dir.glob('VoxCaps-Client-*.zip'))

    with zipfile.ZipFile(full_zip) as full, zipfile.ZipFile(client_zip) as client:
        full_names = set(full.namelist())
        client_names = set(client.namelist())
        for required in ('start_client.exe', 'start_server.exe', 'config_server.py'):
            _member(full, 'VoxCaps', required)
        for required in GGUF_RUNTIME_FILES:
            _member(full, 'VoxCaps', required)
        for required in SERVER_RUNTIME_FILES:
            _member(full, 'VoxCaps', required)
        _member(client, 'VoxCaps-Client', 'start_client.exe')
        for forbidden in ('start_server.exe', 'config_server.py'):
            forbidden_name = f'VoxCaps-Client/{forbidden}'
            if forbidden_name in client_names:
                raise RuntimeError(f'纯客户端包不应包含：{forbidden_name}')

        for relative in SHARED_FILES:
            full_data = _member(full, 'VoxCaps', relative)
            client_data = _member(client, 'VoxCaps-Client', relative)
            if full_data != client_data:
                raise RuntimeError(f'两个发行包的共享文件不一致：{relative}')

        _verify_runtime_version(
            _member(client, 'VoxCaps-Client', 'config_client.py'),
            'config_client.py',
        )
        _verify_runtime_version(
            _member(full, 'VoxCaps', 'config_server.py'),
            'config_server.py',
        )

        icon_data = _member(client, 'VoxCaps-Client', 'assets/icon.ico')
        with Image.open(io.BytesIO(icon_data)) as icon:
            actual_sizes = set(icon.info.get('sizes', set()))
            if actual_sizes != REQUIRED_ICON_SIZES:
                raise RuntimeError(f'ZIP 内 ICO 图层不完整：{sorted(actual_sizes)}')

        if not full_names or not client_names:
            raise RuntimeError('ZIP 内容为空')

    print(f'[VoxCaps] 完整包检查通过：{full_zip}')
    print(f'[VoxCaps] 纯客户端包检查通过：{client_zip}')
    return full_zip, client_zip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-dir', type=Path, default=Path('release'))
    parser.add_argument('--package-root', type=Path)
    args = parser.parse_args()
    if args.package_root:
        verify_full_package_root(args.package_root)
        return
    verify_packages(args.release_dir.resolve())


if __name__ == '__main__':
    main()
