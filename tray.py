import threading
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - optional dependency
    pystray = None
    Image = None
    ImageDraw = None


class TrayIcon:
    def __init__(self, on_open: Callable[[], None], on_exit: Callable[[], None]) -> None:
        self.on_open = on_open
        self.on_exit = on_exit
        self._is_running = False
        self.icon: Optional["pystray.Icon"] = None
        if pystray is not None and Image is not None:
            self.icon = pystray.Icon("TibiaSearch", self._create_image(), "Tibia Search", self._create_menu())

    def _create_image(self) -> "Image.Image":
        size = 64
        image = Image.new("RGBA", (size, size), (30, 30, 30, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, size - 8, size - 8), fill=(173, 214, 255, 255))
        draw.text((18, 18), "T", fill=(0, 0, 0, 255))
        return image

    def _create_menu(self) -> "pystray.Menu":
        return pystray.Menu(
            pystray.MenuItem("Open", self._handle_open),
            pystray.MenuItem("Exit", self._handle_exit),
        )

    def _handle_open(self, _icon: "pystray.Icon", _item: "pystray.MenuItem") -> None:
        self.on_open()

    def _handle_exit(self, _icon: "pystray.Icon", _item: "pystray.MenuItem") -> None:
        self.on_exit()

    def show(self) -> None:
        if self._is_running or self.icon is None:
            return
        self._is_running = True
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self) -> None:
        if self._is_running and self.icon is not None:
            self.icon.stop()
            self._is_running = False

    @property
    def available(self) -> bool:
        return self.icon is not None
