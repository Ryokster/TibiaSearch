from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable

from modules.grid_overlay import GridOverlay


class GridConeOverlay:
    DIRECTIONS = ("UP", "RIGHT", "DOWN", "LEFT")

    def __init__(
        self,
        grid_overlay: GridOverlay | None = None,
        on_change: Callable[[], None] | None = None,
        *,
        pattern: tuple[int, ...] = (1, 3, 3, 5, 5),
        title: str = "Cone Overlay",
    ) -> None:
        self.grid_overlay: GridOverlay | None = None
        self.enabled = False
        self.direction = "UP"
        self.line_color = "#cc3333"
        self.pattern = pattern
        self.title = title
        self._settings_vars: dict[str, tk.Variable] = {}
        self._suppress_ui = False
        self._on_change = on_change
        self._hatch_step = 6

        if grid_overlay is not None:
            self.bind(grid_overlay)

    def bind(self, grid_overlay_instance: GridOverlay) -> None:
        if self.grid_overlay is grid_overlay_instance:
            return
        if self.grid_overlay is not None:
            self.grid_overlay.unregister_painter(self.draw)
        self.grid_overlay = grid_overlay_instance
        self.grid_overlay.register_painter(self.draw)
        self.request_repaint()

    def shutdown(self) -> None:
        if self.grid_overlay is not None:
            self.grid_overlay.unregister_painter(self.draw)
        self.grid_overlay = None

    def build_settings_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=self.title)
        frame.columnconfigure(1, weight=1)

        enabled_var = tk.BooleanVar(value=self.enabled)

        self._settings_vars = {"enabled": enabled_var}

        ttk.Checkbutton(frame, text="Enabled", variable=enabled_var, command=self._apply_from_ui).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(6, 2),
        )

        enabled_var.trace_add("write", lambda *_args: self._apply_from_ui())

        return frame

    def _apply_from_ui(self) -> None:
        if self._suppress_ui or not self._settings_vars:
            return
        enabled = bool(self._settings_vars["enabled"].get())
        self.apply_settings(enabled=enabled)

    def apply_settings(
        self,
        *,
        enabled: bool | None = None,
        direction: str | None = None,
        notify: bool = True,
    ) -> None:
        changed = False

        if enabled is not None and enabled != self.enabled:
            self.enabled = enabled
            changed = True
        if direction is not None:
            direction = direction.upper()
            if direction in self.DIRECTIONS and direction != self.direction:
                self.direction = direction
                changed = True

        if not changed:
            return

        self._sync_ui()
        self.request_repaint()
        if notify and self._on_change:
            self._on_change()

    def _sync_ui(self) -> None:
        if not self._settings_vars:
            return
        self._suppress_ui = True
        try:
            self._settings_vars["enabled"].set(self.enabled)
        finally:
            self._suppress_ui = False

    def set_enabled(self, enabled: bool) -> None:
        self.apply_settings(enabled=enabled)

    def set_direction(self, direction: str) -> None:
        self.apply_settings(direction=direction)

    def compute_cells(self) -> set[tuple[int, int]]:
        grid = self.grid_overlay
        if not grid:
            return set()

        cells: set[tuple[int, int]] = set()
        for index, width in enumerate(self.pattern):
            step = index + 1
            offsets = self._offsets_for_width(width)
            if self.direction == "UP":
                y = -step
                for dx in offsets:
                    self._add_cell_if_in_range(cells, dx, y, grid)
            elif self.direction == "DOWN":
                y = step
                for dx in offsets:
                    self._add_cell_if_in_range(cells, dx, y, grid)
            elif self.direction == "LEFT":
                x = -step
                for dy in offsets:
                    self._add_cell_if_in_range(cells, x, dy, grid)
            elif self.direction == "RIGHT":
                x = step
                for dy in offsets:
                    self._add_cell_if_in_range(cells, x, dy, grid)

        return cells

    def _offsets_for_width(self, width: int) -> Iterable[int]:
        half = width // 2
        return range(-half, half + 1)

    def _add_cell_if_in_range(
        self,
        cells: set[tuple[int, int]],
        x: int,
        y: int,
        grid: GridOverlay,
    ) -> None:
        if -grid.range_x <= x <= grid.range_x and -grid.range_y <= y <= grid.range_y:
            cells.add((x, y))

    def draw(self, canvas: tk.Canvas) -> None:
        grid = self.grid_overlay
        if not self.enabled or not grid or not grid.enabled:
            return
        for cell_x, cell_y in self.compute_cells():
            x1, y1, x2, y2 = grid.get_cell_rect(cell_x, cell_y)
            self._draw_hatch(canvas, x1, y1, x2, y2)

    def _draw_hatch(self, canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int) -> None:
        step = max(2, self._hatch_step)
        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return

        x = x1
        while x < x2:
            length = min(x2 - x, height)
            canvas.create_line(
                x,
                y1,
                x + length,
                y1 + length,
                fill=self.line_color,
                width=1,
                tags="overlay",
            )
            x += step

        y = y1 + step
        while y < y2:
            length = min(width, y2 - y)
            canvas.create_line(
                x1,
                y,
                x1 + length,
                y + length,
                fill=self.line_color,
                width=1,
                tags="overlay",
            )
            y += step

    def request_repaint(self) -> None:
        if self.grid_overlay:
            self.grid_overlay.request_repaint()
