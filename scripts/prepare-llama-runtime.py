"""Download and verify the pinned llama.cpp Vulkan runtime for Windows builds."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from llama_runtime_manifest import (
    LLAMA_RUNTIME_ASSET,
    LLAMA_RUNTIME_MARKER,
    LLAMA_RUNTIME_RELATIVE_DIR,
    LLAMA_RUNTIME_SHA256,
    LLAMA_RUNTIME_TAG,
    LLAMA_RUNTIME_URL,
    REQUIRED_LLAMA_DLLS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_is_ready(runtime_dir: Path) -> bool:
    marker = runtime_dir / LLAMA_RUNTIME_MARKER
    if not marker.is_file():
        return False
    try:
        metadata = json.loads(marker.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return (
        metadata.get('tag') == LLAMA_RUNTIME_TAG
        and metadata.get('sha256') == LLAMA_RUNTIME_SHA256
        and all((runtime_dir / name).is_file() for name in REQUIRED_LLAMA_DLLS)
    )


def download_asset(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'VoxCaps-build'})
    with urllib.request.urlopen(request) as response, destination.open('wb') as output:
        shutil.copyfileobj(response, output)


def prepare_runtime(project_root: Path, cache_dir: Path) -> Path:
    runtime_dir = project_root / LLAMA_RUNTIME_RELATIVE_DIR
    if runtime_is_ready(runtime_dir):
        print(f'[VoxCaps] llama.cpp Vulkan 运行库已就绪：{runtime_dir}')
        return runtime_dir

    asset_path = cache_dir / LLAMA_RUNTIME_ASSET
    if not asset_path.is_file() or sha256(asset_path) != LLAMA_RUNTIME_SHA256:
        with tempfile.NamedTemporaryFile(
            prefix='voxcaps-llama-', suffix='.zip', delete=False, dir=cache_dir
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            print(f'[VoxCaps] 正在下载 llama.cpp Vulkan 运行库：{LLAMA_RUNTIME_URL}')
            download_asset(LLAMA_RUNTIME_URL, temporary_path)
            actual_hash = sha256(temporary_path)
            if actual_hash != LLAMA_RUNTIME_SHA256:
                raise RuntimeError(
                    f'llama.cpp 运行库 SHA-256 不匹配：{actual_hash}'
                )
            temporary_path.replace(asset_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    runtime_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(asset_path) as archive:
        members = {
            Path(info.filename).name: info
            for info in archive.infolist()
            if not info.is_dir()
        }
        missing = [name for name in REQUIRED_LLAMA_DLLS if name not in members]
        if missing:
            raise RuntimeError(f'llama.cpp 官方压缩包缺少 DLL：{missing}')
        for name in REQUIRED_LLAMA_DLLS:
            with archive.open(members[name]) as source, (runtime_dir / name).open('wb') as target:
                shutil.copyfileobj(source, target)

    marker = {
        'tag': LLAMA_RUNTIME_TAG,
        'asset': LLAMA_RUNTIME_ASSET,
        'sha256': LLAMA_RUNTIME_SHA256,
    }
    (runtime_dir / LLAMA_RUNTIME_MARKER).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(f'[VoxCaps] llama.cpp Vulkan 运行库准备完成：{runtime_dir}')
    return runtime_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        '--cache-dir',
        type=Path,
        default=PROJECT_ROOT / '.cache' / 'llama.cpp',
    )
    args = parser.parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    prepare_runtime(args.project_root.resolve(), args.cache_dir.resolve())


if __name__ == '__main__':
    main()
