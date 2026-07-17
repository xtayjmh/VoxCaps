"""从 VoxCaps 规范化几何生成 Windows 多尺寸 ICO。

SVG 是可编辑设计源；这里复用相同坐标和配色，并针对每一尺寸独立超采样，
避免从单张位图连续缩放导致 16px 图层发糊。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'assets' / 'icon.ico'
SIZES = (16, 24, 32, 48, 64, 128, 256)
SUPERSAMPLE = 4


def _mix(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float):
    return tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))


def _draw_layer(size: int) -> Image.Image:
    scale = size * SUPERSAMPLE / 256
    canvas_size = size * SUPERSAMPLE
    image = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(x1: float, y1: float, x2: float, y2: float):
        return tuple(round(value * scale) for value in (x1, y1, x2, y2))

    # 纯色近似 SVG 背景渐变，保持小尺寸轮廓干净稳定。
    draw.rounded_rectangle(
        box(8, 8, 248, 248),
        radius=round(54 * scale),
        fill=(10, 15, 29, 255),
        outline=(38, 54, 83, 255),
        width=max(1, round(2 * scale)),
    )

    bars = (
        (52, 86, 76, 138),
        (84, 69, 108, 169),
        (116, 52, 140, 202),
        (148, 69, 172, 169),
        (180, 86, 204, 138),
    )
    start = (8, 226, 242)
    end = (106, 99, 255)
    for index, coordinates in enumerate(bars):
        color = _mix(start, end, index / (len(bars) - 1)) + (255,)
        draw.rounded_rectangle(
            box(*coordinates),
            radius=round(12 * scale),
            fill=color,
        )

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    layers = [_draw_layer(size) for size in SIZES]
    largest = layers[-1]
    largest.save(
        OUTPUT,
        format='ICO',
        append_images=layers[:-1],
        sizes=[(size, size) for size in SIZES],
        bitmap_format='png',
    )
    print(f'[VoxCaps] 已生成多尺寸图标：{OUTPUT}')


if __name__ == '__main__':
    main()
