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
        self.opacity = 50
        self.stipple = self._opacity_to_stipple(self.opacity)
        self.window_alpha = 100
        self.frame_color = "#ffffff"
        self.frame_width = 5
        self.hatch_step = 6
        self.pattern = pattern
        self.title = title
        self._settings_vars: dict[str, tk.Variable] = {}
        self._suppress_ui = False
        self._on_change = on_change
        self._window: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._transparent_color = "#00ff00"

        if grid_overlay is not None:
            self.bind(grid_overlay)

    def bind(self, grid_overlay_instance: GridOverlay) -> None:
        if self.grid_overlay is grid_overlay_instance:
            return
        if self.grid_overlay is not None:
            self.grid_overlay.unregister_change_listener(self._on_grid_change)
        self.grid_overlay = grid_overlay_instance
        self.grid_overlay.register_change_listener(self._on_grid_change)
        self._sync_visibility()

    def shutdown(self) -> None:
        if self.grid_overlay is not None:
            self.grid_overlay.unregister_change_listener(self._on_grid_change)
        self.grid_overlay = None
        if self._window and self._window.winfo_exists():
            self._window.destroy()
        self._window = None
        self._canvas = None

    def build_settings_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=self.title)
        frame.columnconfigure(1, weight=1)

        enabled_var = tk.BooleanVar(value=self.enabled)
        opacity_var = tk.StringVar(value=str(self.opacity))
        window_alpha_var = tk.StringVar(value=str(self.window_alpha))
        frame_color_var = tk.StringVar(value=self.frame_color)
        frame_width_var = tk.StringVar(value=str(self.frame_width))
        hatch_step_var = tk.StringVar(value=str(self.hatch_step))

        self._settings_vars = {
            "enabled": enabled_var,
            "opacity": opacity_var,
            "window_alpha": window_alpha_var,
            "frame_color": frame_color_var,
            "frame_width": frame_width_var,
            "hatch_step": hatch_step_var,
        }

        ttk.Checkbutton(frame, text="Enabled", variable=enabled_var, command=self._apply_from_ui).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(6, 2),
        )

        ttk.Label(frame, text="Line Opacity").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        opacity_combo = ttk.Combobox(
            frame,
            textvariable=opacity_var,
            values=("100", "75", "50", "25"),
            width=6,
            state="readonly",
        )
        opacity_combo.grid(row=1, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="Overlay Opacity").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        window_alpha_combo = ttk.Combobox(
            frame,
            textvariable=window_alpha_var,
            values=("100", "75", "50", "25"),
            width=6,
            state="readonly",
        )
        window_alpha_combo.grid(row=2, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="Frame Color").grid(row=3, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(frame, textvariable=frame_color_var, width=10).grid(
            row=3, column=1, sticky="w", padx=6, pady=2
        )

        ttk.Label(frame, text="Frame Width").grid(row=4, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(frame, textvariable=frame_width_var, width=6).grid(
            row=4, column=1, sticky="w", padx=6, pady=2
        )

        ttk.Label(frame, text="Hatch Density").grid(row=5, column=0, sticky="w", padx=6, pady=(2, 6))
        ttk.Entry(frame, textvariable=hatch_step_var, width=6).grid(
            row=5, column=1, sticky="w", padx=6, pady=(2, 6)
        )

        enabled_var.trace_add("write", lambda *_args: self._apply_from_ui())
        opacity_var.trace_add("write", lambda *_args: self._apply_from_ui())
        window_alpha_var.trace_add("write", lambda *_args: self._apply_from_ui())
        frame_color_var.trace_add("write", lambda *_args: self._apply_from_ui())
        frame_width_var.trace_add("write", lambda *_args: self._apply_from_ui())
        hatch_step_var.trace_add("write", lambda *_args: self._apply_from_ui())

        return frame

    def _apply_from_ui(self) -> None:
        if self._suppress_ui or not self._settings_vars:
            return
        enabled = bool(self._settings_vars["enabled"].get())
        opacity_raw = str(self._settings_vars["opacity"].get()).strip()
        window_alpha_raw = str(self._settings_vars["window_alpha"].get()).strip()
        frame_color = str(self._settings_vars["frame_color"].get()).strip()
        frame_width_raw = str(self._settings_vars["frame_width"].get()).strip()
        hatch_step_raw = str(self._settings_vars["hatch_step"].get()).strip()
        try:
            opacity = int(opacity_raw)
        except (TypeError, ValueError):
            opacity = None
        try:
            window_alpha = int(window_alpha_raw)
        except (TypeError, ValueError):
            window_alpha = None
        try:
            frame_width = int(frame_width_raw)
        except (TypeError, ValueError):
            frame_width = None
        try:
            hatch_step = int(hatch_step_raw)
        except (TypeError, ValueError):
            hatch_step = None
        self.apply_settings(
            enabled=enabled,
            opacity=opacity,
            window_alpha=window_alpha,
            frame_color=frame_color or None,
            frame_width=frame_width,
            hatch_step=hatch_step,
        )

    def apply_settings(
        self,
        *,
        enabled: bool | None = None,
        direction: str | None = None,
        opacity: int | None = None,
        window_alpha: int | None = None,
        frame_color: str | None = None,
        frame_width: int | None = None,
        hatch_step: int | None = None,
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
        if opacity is not None:
            opacity = max(25, min(100, opacity))
            if opacity != self.opacity:
                self.opacity = opacity
                self.stipple = self._opacity_to_stipple(self.opacity)
                changed = True
        if window_alpha is not None:
            window_alpha = max(25, min(100, window_alpha))
            if window_alpha != self.window_alpha:
                self.window_alpha = window_alpha
                self._apply_window_alpha()
                changed = True
        if frame_color is not None and frame_color != self.frame_color:
            self.frame_color = frame_color
            changed = True
        if frame_width is not None:
            frame_width = max(0, min(10, frame_width))
            if frame_width != self.frame_width:
                self.frame_width = frame_width
                changed = True
        if hatch_step is not None:
            hatch_step = max(2, min(20, hatch_step))
            if hatch_step != self.hatch_step:
                self.hatch_step = hatch_step
                changed = True

        if not changed:
            return

        self._sync_ui()
        self._sync_visibility()
        if notify and self._on_change:
            self._on_change()

    def _sync_ui(self) -> None:
        if not self._settings_vars:
            return
        self._suppress_ui = True
        try:
            self._settings_vars["enabled"].set(self.enabled)
            self._settings_vars["opacity"].set(str(self.opacity))
            self._settings_vars["window_alpha"].set(str(self.window_alpha))
            self._settings_vars["frame_color"].set(self.frame_color)
            self._settings_vars["frame_width"].set(str(self.frame_width))
            self._settings_vars["hatch_step"].set(str(self.hatch_step))
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
        self._repaint()

    def _draw_hatch(self, canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int) -> None:
        step = max(2, self.hatch_step)
        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return

        if self.frame_width > 0:
            canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=self.frame_color,
                width=self.frame_width,
                tags="overlay",
            )

        line_width = self._line_width_for_opacity(self.opacity)
        x = x1
        while x < x2:
            length = min(x2 - x, height)
            line_kwargs = {
                "fill": self.line_color,
                "width": line_width,
                "tags": "overlay",
            }
            if self.stipple:
                line_kwargs["stipple"] = self.stipple
            canvas.create_line(x, y1, x + length, y1 + length, **line_kwargs)
            x += step

        y = y1 + step
        while y < y2:
            length = min(width, y2 - y)
            line_kwargs = {
                "fill": self.line_color,
                "width": line_width,
                "tags": "overlay",
            }
            if self.stipple:
                line_kwargs["stipple"] = self.stipple
            canvas.create_line(x1, y, x1 + length, y + length, **line_kwargs)
            y += step

    def request_repaint(self) -> None:
        if self.enabled:
            self._repaint()

    def _on_grid_change(self) -> None:
        if self.enabled:
            self._repaint()

    def _ensure_window(self) -> None:
        if self._window and self._window.winfo_exists():
            return
        if not self.grid_overlay:
            return
        window = tk.Toplevel(self.grid_overlay.root)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=self._transparent_color)
        try:
            window.attributes("-transparentcolor", self._transparent_color)
        except tk.TclError:
            pass
        self._window = window
        self._canvas = tk.Canvas(window, bg=self._transparent_color, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._apply_window_alpha()

    def _apply_window_alpha(self) -> None:
        if not self._window or not self._window.winfo_exists():
            return
        try:
            self._window.attributes("-alpha", self.window_alpha / 100.0)
        except tk.TclError:
            pass

    def _sync_visibility(self) -> None:
        if not self.enabled or not self.grid_overlay:
            self._hide()
            return
        self._ensure_window()
        self._show()
        self._repaint()

    def _show(self) -> None:
        if not self._window or not self._window.winfo_exists():
            return
        self._window.deiconify()
        self._window.lift()

    def _hide(self) -> None:
        if self._window and self._window.winfo_exists():
            self._window.withdraw()

    def _repaint(self) -> None:
        if not self.enabled or not self.grid_overlay or not self._canvas or not self._window:
            return
        screen_width = self.grid_overlay.root.winfo_screenwidth()
        screen_height = self.grid_overlay.root.winfo_screenheight()
        self._window.geometry(f"{screen_width}x{screen_height}+0+0")
        self._canvas.config(width=screen_width, height=screen_height)
        self._canvas.delete("overlay")

        for cell_x, cell_y in self.compute_cells():
            x1, y1, x2, y2 = self.grid_overlay.get_cell_rect(cell_x, cell_y)
            self._draw_hatch(self._canvas, x1, y1, x2, y2)

        self._canvas.update_idletasks()

    @staticmethod
    def _opacity_to_stipple(opacity: int) -> str:
        if opacity >= 100:
            return ""
        if opacity >= 75:
            return "gray75"
        if opacity >= 50:
            return "gray50"
        return "gray50"

    @staticmethod
    def _line_width_for_opacity(opacity: int) -> int:
        if opacity >= 100:
            return 2
        if opacity >= 75:
            return 1
        return 1
