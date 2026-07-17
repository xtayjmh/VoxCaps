"""基于 Tkinter 的无边框动态状态岛。"""

from __future__ import annotations

import math
import ctypes
import tkinter as tk
from queue import Empty, Queue
from threading import Event
from time import monotonic

from core.ui.window_icon import apply_window_icon

from .state_machine import IslandEvent, IslandStage, IslandStateMachine


class DynamicIslandView:
    FRAME_MS = 30
    TRANSPARENT = '#010203'

    def __init__(
        self,
        events: Queue[IslandEvent],
        stop_event: Event,
        width: int,
        height: int,
        bottom_margin: int,
    ) -> None:
        self.events = events
        self.stop_event = stop_event
        self.width = width
        self.height = height
        self.bottom_margin = bottom_margin
        self.machine = IslandStateMachine()
        self.root: tk.Tk | None = None
        self.canvas: tk.Canvas | None = None
        self.visible = False
        self.phase = 0.0

    def run(self) -> None:
        root = tk.Tk()
        self.root = root
        root.title('VoxCaps Dynamic Island')
        apply_window_icon(root)
        root.withdraw()
        root.overrideredirect(True)
        root.configure(bg=self.TRANSPARENT)
        root.attributes('-topmost', True)
        try:
            root.wm_attributes('-transparentcolor', self.TRANSPARENT)
        except tk.TclError:
            pass

        canvas = tk.Canvas(
            root,
            width=self.width,
            height=self.height,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack()
        self.canvas = canvas

        root.update_idletasks()
        left, top, right, bottom = self._get_work_area(
            root.winfo_screenwidth(),
            root.winfo_screenheight(),
        )
        x, y = self._calculate_position(
            (left, top, right, bottom),
            self.width,
            self.height,
            self.bottom_margin,
        )
        root.geometry(f'{self.width}x{self.height}+{x}+{y}')
        root.after(self.FRAME_MS, self._tick)
        root.mainloop()

    def _tick(self) -> None:
        if self.stop_event.is_set():
            if self.root:
                self.root.destroy()
            return

        now = monotonic()
        self._drain_events()
        state = self.machine.state

        if state.stage in (
            IslandStage.PREPARING,
            IslandStage.RECORDING,
            IslandStage.RECOGNIZING,
        ):
            self._show()
        elif state.stage is IslandStage.IDLE:
            self._hide()

        if self.visible:
            self.phase += 0.19
            self._draw(state.stage)

        if self.root:
            self.root.after(self.FRAME_MS, self._tick)

    def _drain_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except Empty:
                return

            self.machine.apply(event)

    def _show(self) -> None:
        if self.visible or not self.root:
            return
        self.visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.attributes('-topmost', True)

    def _hide(self) -> None:
        if not self.visible or not self.root:
            return
        self.visible = False
        self.root.withdraw()

    def _draw(self, stage: IslandStage) -> None:
        canvas = self.canvas
        if not canvas:
            return
        canvas.delete('all')
        border = '#4f535b'
        fill = '#050505'
        self._rounded_rect(0, 0, self.width - 1, self.height - 1, fill, border)

        colors = self._wave_colors(stage)
        if colors:
            self._draw_wave(*colors)
        elif stage is IslandStage.RECOGNIZING:
            self._draw_recognizing()

    @staticmethod
    def _wave_colors(stage: IslandStage) -> tuple[str, str] | None:
        if stage is IslandStage.PREPARING:
            return '#ffb43b', '#ff7a45'
        if stage is IslandStage.RECORDING:
            return '#12d4e8', '#4b79ff'
        return None

    @staticmethod
    def _get_work_area(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
        """返回 Windows 可用工作区，排除任务栏占用区域。"""
        if hasattr(ctypes, 'windll'):
            class Rect(ctypes.Structure):
                _fields_ = [
                    ('left', ctypes.c_long),
                    ('top', ctypes.c_long),
                    ('right', ctypes.c_long),
                    ('bottom', ctypes.c_long),
                ]

            rect = Rect()
            try:
                if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                    return rect.left, rect.top, rect.right, rect.bottom
            except (AttributeError, OSError):
                pass
        return 0, 0, screen_width, screen_height

    @staticmethod
    def _calculate_position(
        work_area: tuple[int, int, int, int],
        width: int,
        height: int,
        bottom_margin: int,
    ) -> tuple[int, int]:
        left, top, right, bottom = work_area
        x = max(left, left + (right - left - width) // 2)
        y = max(top, bottom - height - bottom_margin)
        return x, y

    def _rounded_rect(self, x1, y1, x2, y2, fill: str, outline: str) -> None:
        # 外层与内层都使用单一多边形轮廓，不再拼接矩形和椭圆，
        # 从根源上避免 Tk 栅格化造成的接缝错位。
        border_width = max(1, round(self.height / 34))
        self._pill_shape(x1, y1, x2, y2, outline)
        self._pill_shape(
            x1 + border_width,
            y1 + border_width,
            x2 - border_width,
            y2 - border_width,
            fill,
        )

    def _pill_shape(self, x1, y1, x2, y2, fill: str) -> None:
        canvas = self.canvas
        if not canvas:
            return
        points = self._rounded_polygon_points(x1, y1, x2, y2)
        canvas.create_polygon(points, fill=fill, outline='')

    @staticmethod
    def _rounded_polygon_points(x1, y1, x2, y2) -> list[float]:
        """生成略小于半圆的圆角矩形轮廓点。"""
        width = x2 - x1
        height = y2 - y1
        radius = max(8.0, min(height * 0.44, width / 2))
        corners = (
            (x2 - radius, y1 + radius, -90, 0),
            (x2 - radius, y2 - radius, 0, 90),
            (x1 + radius, y2 - radius, 90, 180),
            (x1 + radius, y1 + radius, 180, 270),
        )
        points: list[float] = []
        steps = 12
        for center_x, center_y, start, end in corners:
            for step in range(steps + 1):
                angle = math.radians(start + (end - start) * step / steps)
                points.extend((
                    center_x + radius * math.cos(angle),
                    center_y + radius * math.sin(angle),
                ))
        return points

    def _draw_wave(self, start: str, end: str) -> None:
        canvas = self.canvas
        if not canvas:
            return
        count = 23
        inner_width = self.width * 0.72
        center_x = self.width / 2
        center_y = self.height / 2
        gap = inner_width / (count - 1)
        for index in range(count):
            distance = abs((index - (count - 1) / 2) / ((count - 1) / 2))
            envelope = 0.24 + 0.76 * (1.0 - distance ** 1.35)
            signal = abs(
                math.sin(self.phase + index * 0.58)
                + 0.42 * math.sin(self.phase * 1.73 - index * 0.37)
            ) / 1.42
            bar_height = 3 + (self.height - 9) * envelope * (0.2 + 0.8 * signal)
            x = center_x - inner_width / 2 + index * gap
            color = self._mix(start, end, index / (count - 1))
            canvas.create_line(
                x,
                center_y - bar_height / 2,
                x,
                center_y + bar_height / 2,
                fill=color,
                width=max(2, round(self.height / 17)),
                capstyle=tk.ROUND,
            )

    def _draw_recognizing(self) -> None:
        canvas = self.canvas
        if not canvas:
            return
        center_y = self.height / 2
        count = 7
        for index in range(count):
            pulse = (math.sin(self.phase - index * 0.72) + 1) / 2
            scale = self.height / 34
            radius = (1.4 + 1.8 * pulse) * scale
            color = self._mix('#5c6cff', '#c066ff', pulse)
            x = self.width / 2 + (index - (count - 1) / 2) * 9 * scale
            canvas.create_oval(
                x - radius,
                center_y - radius,
                x + radius,
                center_y + radius,
                fill=color,
                outline='',
            )

    @staticmethod
    def _mix(start: str, end: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        start_rgb = tuple(int(start[i:i + 2], 16) for i in (1, 3, 5))
        end_rgb = tuple(int(end[i:i + 2], 16) for i in (1, 3, 5))
        rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
