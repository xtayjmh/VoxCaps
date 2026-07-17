"""校验 VoxCaps 品牌源文件、ICO 图层及 Windows EXE 图标资源。"""

from __future__ import annotations

import argparse
import ctypes
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / 'assets' / 'voxcaps-icon.svg'
ICO_PATH = ROOT / 'assets' / 'icon.ico'
REQUIRED_SIZES = {
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
}


def verify_svg() -> None:
    root = ET.parse(SVG_PATH).getroot()
    elements = list(root.iter())
    if root.attrib.get('viewBox') != '0 0 256 256':
        raise RuntimeError('SVG viewBox 必须为 0 0 256 256')
    if any(node.tag.endswith(('text', 'image')) for node in elements):
        raise RuntimeError('SVG 不得依赖文字或外部图片')
    if not any(node.tag.endswith('linearGradient') for node in elements):
        raise RuntimeError('SVG 缺少品牌渐变定义')


def verify_ico() -> None:
    with Image.open(ICO_PATH) as image:
        actual_sizes = set(image.info.get('sizes', set()))
        if actual_sizes != REQUIRED_SIZES:
            raise RuntimeError(
                f'ICO 图层不完整：实际 {sorted(actual_sizes)}，'
                f'期望 {sorted(REQUIRED_SIZES)}'
            )
        for size in REQUIRED_SIZES:
            layer = image.ico.getimage(size)
            if layer.size != size or layer.mode != 'RGBA':
                raise RuntimeError(f'ICO 图层 {size} 不是有效 RGBA 图像')


def verify_executable(executable: Path) -> None:
    if os.name != 'nt':
        raise RuntimeError('EXE 图标资源检查只能在 Windows 上运行')
    if not executable.is_file():
        raise FileNotFoundError(f'构建产物不存在：{executable}')

    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    shell32.ExtractIconExW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint,
    ]
    shell32.ExtractIconExW.restype = ctypes.c_uint
    count = shell32.ExtractIconExW(str(executable), -1, None, None, 0)
    if count < 1:
        raise RuntimeError(f'EXE 未发现图标资源：{executable}')

    large = ctypes.c_void_p()
    small = ctypes.c_void_p()
    extracted = shell32.ExtractIconExW(
        str(executable),
        0,
        ctypes.byref(large),
        ctypes.byref(small),
        1,
    )
    try:
        if extracted != 1 or not large.value or not small.value:
            raise RuntimeError(f'EXE 大/小图标资源不完整：{executable}')
    finally:
        if large.value:
            user32.DestroyIcon(large)
        if small.value:
            user32.DestroyIcon(small)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--executables', nargs='*', type=Path, default=[])
    args = parser.parse_args()

    verify_svg()
    verify_ico()
    for executable in args.executables:
        verify_executable((ROOT / executable).resolve())
    print('[VoxCaps] 品牌 SVG、ICO 与构建产物图标检查通过。')


if __name__ == '__main__':
    main()
