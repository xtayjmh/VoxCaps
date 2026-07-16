"""基于 Tkinter 的无边框动态状态岛。"""

from __future__ import annotations

import math
import tkinter as tk
from queue import Empty, Queue
from threading import Event
from time import monotonic

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
        hold_delay_ms: int,
    ) -> None:
        self.events = events
        self.stop_event = stop_event
        self.width = width
        self.height = height
        self.bottom_margin = bottom_margin
        self.hold_delay = hold_delay_ms / 1000.0
        self.machine = IslandStateMachine()
        self.root: tk.Tk | None = None
        self.canvas: tk.Canvas | None = None
        self.visible = False
        self.phase = 0.0
        self.show_at = 0.0
        self.hide_at = 0.0

    def run(self) -> None:
        root = tk.Tk()
        self.root = root
        root.title('CapsWriter Dynamic Island')
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
        x = max(0, (root.winfo_screenwidth() - self.width) // 2)
        y = max(0, root.winfo_screenheight() - self.height - self.bottom_margin)
        root.geometry(f'{self.width}x{self.height}+{x}+{y}')
        root.after(self.FRAME_MS, self._tick)
        root.mainloop()

    def _tick(self) -> None:
        if self.stop_event.is_set():
            if self.root:
                self.root.destroy()
            return

        now = monotonic()
        self._drain_events(now)
        state = self.machine.state

        if state.stage is IslandStage.RECORDING and now >= self.show_at:
            self._show()
        elif state.stage in (
            IslandStage.RECOGNIZING,
            IslandStage.DELIVERED,
            IslandStage.ERROR,
        ):
            self._show()
        elif state.stage is IslandStage.IDLE:
            self._hide()

        if self.visible:
            self.phase += 0.19
            self._draw(state.stage, now)

        if self.hide_at and now >= self.hide_at:
            self.machine.apply(IslandEvent(IslandStage.IDLE, state.task_id))
            self.hide_at = 0.0
            self._hide()

        if self.root:
            self.root.after(self.FRAME_MS, self._tick)

    def _drain_events(self, now: float) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except Empty:
                return

            if not self.machine.apply(event):
                continue
            if event.stage is IslandStage.RECORDING:
                self.show_at = now + self.hold_delay
                self.hide_at = 0.0
            elif event.stage is IslandStage.RECOGNIZING:
                self.hide_at = 0.0
            elif event.stage is IslandStage.DELIVERED:
                self.hide_at = now + 0.72
            elif event.stage is IslandStage.ERROR:
                self.hide_at = now + 1.15
            elif event.stage is IslandStage.IDLE:
                self.show_at = 0.0
                self.hide_at = 0.0

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

    def _draw(self, stage: IslandStage, now: float) -> None:
        canvas = self.canvas
        if not canvas:
            return
        canvas.delete('all')
        border = '#4f535b'
        fill = '#050505'
        if stage is IslandStage.ERROR:
            border = '#ff5263'
            fill = '#170609'
        elif stage is IslandStage.DELIVERED:
            border = '#34e6bd'
            fill = '#031310'
        self._rounded_rect(0, 0, self.width - 1, self.height - 1, fill, border)

        if stage is IslandStage.RECORDING:
            self._draw_wave('#12d4e8', '#4b79ff')
        elif stage is IslandStage.RECOGNIZING:
            self._draw_recognizing()
        elif stage is IslandStage.DELIVERED:
            self._draw_delivered(now)
        elif stage is IslandStage.ERROR:
            self._draw_error()

    def _rounded_rect(self, x1, y1, x2, y2, fill: str, outline: str) -> None:
        # 先画一层描边色，再内缩一像素绘制主体，避免完整椭圆的
        # 描边在胶囊内部留下两道竖向弧线。
        self._pill_shape(x1, y1, x2, y2, outline)
        self._pill_shape(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill)

    def _pill_shape(self, x1, y1, x2, y2, fill: str) -> None:
        canvas = self.canvas
        if not canvas:
            return
        radius = max(8, (y2 - y1) / 2)
        canvas.create_rectangle(
            x1 + radius, y1, x2 - radius, y2, fill=fill, outline=''
        )
        canvas.create_rectangle(
            x1, y1 + radius, x2, y2 - radius, fill=fill, outline=''
        )
        canvas.create_oval(
            x1, y1, x1 + 2 * radius, y2, fill=fill, outline=''
        )
        canvas.create_oval(
            x2 - 2 * radius, y1, x2, y2, fill=fill, outline=''
        )

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
                width=2,
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
            radius = 1.4 + 1.8 * pulse
            color = self._mix('#5c6cff', '#c066ff', pulse)
            x = self.width / 2 + (index - (count - 1) / 2) * 9
            canvas.create_oval(
                x - radius,
                center_y - radius,
                x + radius,
                center_y + radius,
                fill=color,
                outline='',
            )

    def _draw_delivered(self, now: float) -> None:
        canvas = self.canvas
        if not canvas:
            return
        elapsed = max(0.0, now - self.machine.state.changed_at)
        progress = min(1.0, elapsed / 0.58)
        left = self.width * 0.15
        right = self.width * 0.85
        head = left + (right - left) * progress
        canvas.create_line(left, self.height / 2, right, self.height / 2, fill='#17483f', width=2)
        canvas.create_line(max(left, head - 28), self.height / 2, head, self.height / 2, fill='#45f6cb', width=3)

    def _draw_error(self) -> None:
        canvas = self.canvas
        if not canvas:
            return
        x = self.width / 2
        y = self.height / 2
        canvas.create_line(x, y - 7, x, y + 2, fill='#ff6878', width=3, capstyle=tk.ROUND)
        canvas.create_oval(x - 1.5, y + 6, x + 1.5, y + 9, fill='#ff6878', outline='')

    @staticmethod
    def _mix(start: str, end: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        start_rgb = tuple(int(start[i:i + 2], 16) for i in (1, 3, 5))
        end_rgb = tuple(int(end[i:i + 2], 16) for i in (1, 3, 5))
        rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
