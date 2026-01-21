from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import ttk
from typing import Callable


class GridOverlay:
    RANGE_X = 7
    RANGE_Y = 5
    MIN_CELL_SIZE = 10
    MAX_CELL_SIZE = 300

    def __init__(self, root: tk.Tk, on_change: Callable[[], None] | None = None) -> None:
        self.root = root
        self.enabled = False
        self.center_x = 0
        self.center_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.cell_size = 50
        self.line_color = "#888888"
        self.range_x = self.RANGE_X
        self.range_y = self.RANGE_Y
        self._window: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._transparent_color = "#00ff00"
        self._settings_vars: dict[str, tk.Variable] = {}
        self._suppress_ui = False
        self._on_change = on_change
        self._extra_painters: list[Callable[[tk.Canvas], None]] = []
        self._aux_visible_sources: set[object] = set()
        self._change_listeners: list[Callable[[], None]] = []

        self._set_default_center()

    def _set_default_center(self) -> None:
        self.root.update_idletasks()
        self.center_x = self.root.winfo_screenwidth() // 2
        self.center_y = self.root.winfo_screenheight() // 2

    def _ensure_window(self) -> None:
        if self._window and self._window.winfo_exists():
            return
        window = tk.Toplevel(self.root)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=self._transparent_color)
        try:
            window.attributes("-transparentcolor", self._transparent_color)
        except tk.TclError:
            pass
        try:
            window.attributes("-alpha", 0.5)
        except tk.TclError:
            pass
        canvas = tk.Canvas(window, bg=self._transparent_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self._window = window
        self._canvas = canvas
        self._set_clickthrough()

    def _set_clickthrough(self) -> None:
        if os.name != "nt" or not self._window or not self._window.winfo_exists():
            return
        try:
            hwnd = self._window.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        except Exception:
            return

    def shutdown(self) -> None:
        if self._window and self._window.winfo_exists():
            self._window.destroy()
        self._window = None
        self._canvas = None
        self._aux_visible_sources.clear()

    def register_painter(self, painter: Callable[[tk.Canvas], None]) -> None:
        if painter in self._extra_painters:
            return
        self._extra_painters.append(painter)
        self.request_repaint()

    def unregister_painter(self, painter: Callable[[tk.Canvas], None]) -> None:
        if painter in self._extra_painters:
            self._extra_painters.remove(painter)
            self.request_repaint()

    def register_change_listener(self, listener: Callable[[], None]) -> None:
        if listener in self._change_listeners:
            return
        self._change_listeners.append(listener)

    def unregister_change_listener(self, listener: Callable[[], None]) -> None:
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def _notify_change_listeners(self) -> None:
        for listener in tuple(self._change_listeners):
            listener()

    def set_auxiliary_visibility(self, source: object, visible: bool) -> None:
        if visible:
            self._aux_visible_sources.add(source)
        else:
            self._aux_visible_sources.discard(source)
        self._sync_visibility()

    def _is_visible(self) -> bool:
        return self.enabled or bool(self._aux_visible_sources)

    def build_settings_frame(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Grid Settings")
        frame.columnconfigure(1, weight=1)

        enabled_var = tk.BooleanVar(value=self.enabled)
        offset_x_var = tk.StringVar(value=str(self.offset_x))
        offset_y_var = tk.StringVar(value=str(self.offset_y))
        cell_size_var = tk.StringVar(value=str(self.cell_size))
        center_x_var = tk.StringVar(value=str(self.center_x))
        center_y_var = tk.StringVar(value=str(self.center_y))
        color_var = tk.StringVar(value=self.line_color)

        self._settings_vars = {
            "enabled": enabled_var,
            "offset_x": offset_x_var,
            "offset_y": offset_y_var,
            "cell_size": cell_size_var,
            "center_x": center_x_var,
            "center_y": center_y_var,
            "line_color": color_var,
        }

        ttk.Checkbutton(frame, text="Enabled", variable=enabled_var, command=self._apply_from_ui).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(6, 2),
        )

        ttk.Label(frame, text="Offset X").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(frame, textvariable=offset_x_var, width=10).grid(row=1, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="Offset Y").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(frame, textvariable=offset_y_var, width=10).grid(row=2, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="Cell Size").grid(row=3, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(frame, textvariable=cell_size_var, width=10).grid(row=3, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="Center X").grid(row=4, column=0, sticky="w", padx=6, pady=2)
        ttk.Entry(frame, textvariable=center_x_var, width=10).grid(row=4, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="Center Y").grid(row=5, column=0, sticky="w", padx=6, pady=(2, 6))
        ttk.Entry(frame, textvariable=center_y_var, width=10).grid(row=5, column=1, sticky="w", padx=6, pady=(2, 6))

        ttk.Label(frame, text="Line Color").grid(row=6, column=0, sticky="w", padx=6, pady=(2, 6))
        ttk.Entry(frame, textvariable=color_var, width=12).grid(row=6, column=1, sticky="w", padx=6, pady=(2, 6))

        for var in (offset_x_var, offset_y_var, cell_size_var, center_x_var, center_y_var, color_var):
            var.trace_add("write", lambda *_args: self._apply_from_ui())

        return frame

    def _parse_int(self, value: str) -> int | None:
        cleaned = value.strip()
        if cleaned in {"", "-", "+"}:
            return None
        try:
            return int(cleaned)
        except (TypeError, ValueError):
            return None

    def _apply_from_ui(self) -> None:
        if self._suppress_ui or not self._settings_vars:
            return
        enabled = bool(self._settings_vars["enabled"].get())
        updates: dict[str, int | bool] = {"enabled": enabled}

        for key in ("offset_x", "offset_y", "center_x", "center_y"):
            raw = str(self._settings_vars[key].get())
            parsed = self._parse_int(raw)
            if parsed is None:
                continue
            updates[key] = parsed

        cell_raw = str(self._settings_vars["cell_size"].get())
        cell_parsed = self._parse_int(cell_raw)
        if cell_parsed is not None:
            cell_parsed = max(self.MIN_CELL_SIZE, min(self.MAX_CELL_SIZE, cell_parsed))
            updates["cell_size"] = cell_parsed

        color_raw = str(self._settings_vars["line_color"].get()).strip()
        if color_raw:
            updates["line_color"] = color_raw

        self.apply_settings(**updates)

    def apply_settings(
        self,
        *,
        enabled: bool | None = None,
        center_x: int | None = None,
        center_y: int | None = None,
        offset_x: int | None = None,
        offset_y: int | None = None,
        cell_size: int | None = None,
        line_color: str | None = None,
        notify: bool = True,
    ) -> None:
        changed = False

        if enabled is not None and enabled != self.enabled:
            self.enabled = enabled
            changed = True
        if center_x is not None and center_x != self.center_x:
            self.center_x = center_x
            changed = True
        if center_y is not None and center_y != self.center_y:
            self.center_y = center_y
            changed = True
        if offset_x is not None and offset_x != self.offset_x:
            self.offset_x = offset_x
            changed = True
        if offset_y is not None and offset_y != self.offset_y:
            self.offset_y = offset_y
            changed = True
        if cell_size is not None:
            cell_size = max(self.MIN_CELL_SIZE, min(self.MAX_CELL_SIZE, cell_size))
            if cell_size != self.cell_size:
                self.cell_size = cell_size
                changed = True
        if line_color is not None and line_color != self.line_color:
            self.line_color = line_color
            changed = True

        if not changed:
            return
        self._sync_visibility()

        self._sync_ui()
        self._notify_change_listeners()
        if notify and self._on_change:
            self._on_change()

    def _sync_visibility(self) -> None:
        if self._is_visible():
            self._ensure_window()
            self._show()
            self._repaint()
        else:
            self._hide()

    def _sync_ui(self) -> None:
        if not self._settings_vars:
            return
        self._suppress_ui = True
        try:
            self._settings_vars["enabled"].set(self.enabled)
            self._settings_vars["offset_x"].set(str(self.offset_x))
            self._settings_vars["offset_y"].set(str(self.offset_y))
            self._settings_vars["cell_size"].set(str(self.cell_size))
            self._settings_vars["center_x"].set(str(self.center_x))
            self._settings_vars["center_y"].set(str(self.center_y))
            self._settings_vars["line_color"].set(self.line_color)
        finally:
            self._suppress_ui = False

    def _show(self) -> None:
        if not self._window or not self._window.winfo_exists():
            return
        self._window.deiconify()
        self._window.lift()

    def _hide(self) -> None:
        if self._window and self._window.winfo_exists():
            self._window.withdraw()

    def _repaint(self) -> None:
        if not self._canvas or not self._window:
            return

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self._window.geometry(f"{screen_width}x{screen_height}+0+0")
        self._canvas.config(width=screen_width, height=screen_height)
        self._canvas.delete("grid")
        self._canvas.delete("overlay")

        origin_x = self.center_x + self.offset_x - (self.range_x * self.cell_size)
        origin_y = self.center_y + self.offset_y - (self.range_y * self.cell_size)
        grid_width = (self.range_x * 2 + 1) * self.cell_size
        grid_height = (self.range_y * 2 + 1) * self.cell_size

        if self.enabled:
            dash_pattern = (4, 4)
            line_color = self.line_color

            for index in range(self.range_x * 2 + 2):
                x = origin_x + index * self.cell_size
                self._canvas.create_line(
                    x,
                    origin_y,
                    x,
                    origin_y + grid_height,
                    fill=line_color,
                    width=1,
                    dash=dash_pattern,
                    tags="grid",
                )

            for index in range(self.range_y * 2 + 2):
                y = origin_y + index * self.cell_size
                self._canvas.create_line(
                    origin_x,
                    y,
                    origin_x + grid_width,
                    y,
                    fill=line_color,
                    width=1,
                    dash=dash_pattern,
                    tags="grid",
                )

        for painter in tuple(self._extra_painters):
            painter(self._canvas)

        self._canvas.update_idletasks()

    def request_repaint(self) -> None:
        if self._is_visible():
            self._repaint()

    def get_origin(self) -> tuple[int, int]:
        origin_x = self.center_x + self.offset_x - (self.range_x * self.cell_size)
        origin_y = self.center_y + self.offset_y - (self.range_y * self.cell_size)
        return origin_x, origin_y

    def get_cell_rect(self, cell_x: int, cell_y: int) -> tuple[int, int, int, int]:
        origin_x, origin_y = self.get_origin()
        x1 = origin_x + (cell_x + self.range_x) * self.cell_size
        y1 = origin_y + (cell_y + self.range_y) * self.cell_size
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size
        return x1, y1, x2, y2

    def get_state(self) -> dict[str, int | bool]:
        return {
            "enabled": self.enabled,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "cell_size": self.cell_size,
            "line_color": self.line_color,
        }
