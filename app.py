import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from urllib.parse import quote, urlencode
from urllib.request import urlopen
import webbrowser

from history import HistoryManager
from tray import TrayIcon

API_ENDPOINT = "https://tibia.fandom.com/api.php"
WIKI_PAGE_URL = "https://tibia.fandom.com/wiki/"
SEARCH_PAGE_URL = "https://tibia.fandom.com/wiki/Special:Search"


class TibiaSearchApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tibia Search")
        self.root.resizable(False, False)

        self.base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        self.history_path = self.base_dir / "history.json"
        self.history = HistoryManager(self.history_path)

        self.tray_icon = TrayIcon(self.show_window, self.exit_app)

        self.always_on_top = False

        self._build_ui()
        self._bind_events()
        self._refresh_history_list()

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.show_window()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)

        top_frame = ttk.Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        top_frame.columnconfigure(0, weight=1)

        self.top_button = tk.Button(
            top_frame,
            text="Top Off",
            width=8,
            relief=tk.RAISED,
            command=self.toggle_topmost,
        )
        self.top_button.grid(row=0, column=1, sticky="e")

        entry_frame = ttk.Frame(self.root)
        entry_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
        entry_frame.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(entry_frame)
        self.search_entry.grid(row=0, column=0, sticky="ew")

        self.search_button = ttk.Button(entry_frame, text="Search", command=self.perform_search)
        self.search_button.grid(row=0, column=1, padx=(6, 0))

        self.history_list = tk.Listbox(self.root, height=6)
        self.history_list.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))

    def _bind_events(self) -> None:
        self.search_entry.bind("<Return>", lambda _event: self.perform_search())
        self.search_entry.bind("<Escape>", lambda _event: self.clear_entry())
        self.history_list.bind("<ButtonRelease-1>", self.load_from_history)
        self.history_list.bind("<Double-Button-1>", lambda _event: self.perform_search())

    def clear_entry(self) -> None:
        self.search_entry.delete(0, tk.END)

    def toggle_topmost(self) -> None:
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        if self.always_on_top:
            self.top_button.config(text="Top On", relief=tk.SUNKEN)
        else:
            self.top_button.config(text="Top Off", relief=tk.RAISED)

    def _refresh_history_list(self) -> None:
        self.history_list.delete(0, tk.END)
        for item in self.history.items:
            self.history_list.insert(tk.END, item)

    def load_from_history(self, _event: tk.Event) -> None:
        selection = self.history_list.curselection()
        if not selection:
            return
        value = self.history_list.get(selection[0])
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, value)

    def perform_search(self) -> None:
        query = self.search_entry.get().strip()
        if not query:
            return

        self.history.add(query)
        self._refresh_history_list()

        if query.startswith("http://") or query.startswith("https://"):
            webbrowser.open(query)
            return

        threading.Thread(target=self._search_wiki, args=(query,), daemon=True).start()

    def _search_wiki(self, query: str) -> None:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
        }
        url = f"{API_ENDPOINT}?{urlencode(params)}"

        try:
            with urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            results = data.get("query", {}).get("search", [])
        except Exception:
            self._open_search_page(query)
            return

        if len(results) == 1:
            title = results[0].get("title", "")
            if title:
                target_url = f"{WIKI_PAGE_URL}{quote(title.replace(' ', '_'))}"
                webbrowser.open(target_url)
                return

        self._open_search_page(query)

    def _open_search_page(self, query: str) -> None:
        target_url = f"{SEARCH_PAGE_URL}?{urlencode({'query': query})}"
        webbrowser.open(target_url)

    def hide_to_tray(self) -> None:
        self.root.withdraw()
        self.tray_icon.show()

    def show_window(self) -> None:
        self.tray_icon.stop()
        self.root.deiconify()
        self.root.lift()
        if self.always_on_top:
            self.root.attributes("-topmost", True)
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)

    def exit_app(self) -> None:
        self.tray_icon.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = TibiaSearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
